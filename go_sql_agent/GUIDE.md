# Практическое руководство: Создание SQL-агента с LLM и инструментами

## Оглавление
1. [Введение](#введение)
2. [Архитектура решения](#архитектура-решения)
3. [Основные проблемы и их решения](#основные-проблемы-и-их-решения)
4. [Пошаговая реализация](#пошаговая-реализация)
5. [Лучшие практики](#лучшие-практики)
6. [Отладка и тестирование](#отладка-и-тестирование)

---

## Введение

Это руководство описывает процесс создания агента на базе LLM (Large Language Model), который может:
- Подключаться к базе данных (PostgreSQL/MySQL)
- Анализировать схему БД
- Использовать инструменты (tools/function calling) для выполнения задач
- Экспортировать данные в CSV с кириллическими заголовками

**Стек технологий:**
- Go 1.25+
- Google ADK (Agent Development Kit)
- OpenAI SDK для взаимодействия с LLM через OpenRouter
- PostgreSQL/MySQL драйверы

---

## Архитектура решения

### Компоненты системы

```
┌─────────────────┐
│   Main App      │
│  (cmd/main.go)  │
└────────┬────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         │              │              │              │
┌────────▼────────┐ ┌──▼──────────┐ ┌─▼──────────┐ ┌─▼──────────┐
│  LLM Client     │ │   Tools     │ │  Config    │ │ CSV Export │
│ (llm_clients.go)│ │ (tools.go)  │ │(config.go) │ │(csv_export)│
└─────────────────┘ └─────────────┘ └────────────┘ └────────────┘
         │                  │
         │                  │
    ┌────▼────┐      ┌──────▼──────┐
    │ OpenAI  │      │  Database   │
    │   API   │      │             │
    └─────────┘      └─────────────┘
```

### Поток данных

```
1. User Request → Agent
2. Agent → LLM (с системным промптом и доступными tools)
3. LLM → JSON вызов функции
4. Agent парсит JSON → выполняет функцию
5. Результат функции → обратно в LLM как контекст
6. Повторяем 3-5 до завершения задачи
```

---

## Основные проблемы и их решения

### Проблема 1: Модель не использует инструменты

**Симптомы:**
```
[medical-data-agent]: Вот SQL запрос для получения данных:
SELECT * FROM diagnoses...
```

**Причина:** Модель генерирует текстовый ответ вместо вызова функций.

**Решение:**

1. **Явные инструкции в системном промпте:**
```go
basePrompt := `КРИТИЧЕСКИ ВАЖНО:
- Вызывай ТОЛЬКО ОДНУ функцию за раз
- Отвечай ТОЛЬКО JSON объектом, БЕЗ дополнительного текста
- НЕ пиши код или SQL в тексте ответа

Формат ответа: {"name": "FunctionName", "arguments": {...}}
`
```

2. **Примеры в промпте:**
```go
ДОСТУПНЫЕ ФУНКЦИИ:

1. GetDatabaseSchema - получает схему БД
   Формат: {"name": "GetDatabaseSchema", "arguments": {}}
   
2. GetTableSample - смотрит данные таблицы  
   Формат: {"name": "GetTableSample", "arguments": {"table_name": "имя_таблицы"}}
```

3. **Пошаговый план:**
```go
ПЛАН РАБОТЫ (следуй строго по шагам):
Шаг 1: Вызови GetDatabaseSchema
Шаг 2: Найди нужные таблицы
Шаг 3: Вызови GetTableSample для каждой таблицы
Шаг 4: Составь SQL и вызови ExecuteQuery
```

### Проблема 2: OpenRouter не поддерживает нативный function calling

**Симптомы:**
```
[DEBUG] ToolCalls count: 0
[DEBUG] Model response content: "{\"name\": \"GetDatabaseSchema\", \"arguments\": {}}"
```

**Причина:** Модель Qwen через OpenRouter возвращает вызовы функций в виде JSON-текста, а не через `ToolCalls` API.

**Решение - парсинг JSON из текста:**

```go
// В llm_clients.go
if len(choice.Message.ToolCalls) > 0 {
    // Нативный OpenAI function calling
    for _, tc := range choice.Message.ToolCalls {
        var args map[string]interface{}
        json.Unmarshal([]byte(tc.Function.Arguments), &args)
        parts = append(parts, &genai.Part{
            FunctionCall: &genai.FunctionCall{
                Name: tc.Function.Name,
                Args: args,
            },
        })
    }
} else if choice.Message.Content != "" {
    // Парсим JSON из текста
    var funcCall struct {
        Name      string                 `json:"name"`
        Arguments map[string]interface{} `json:"arguments"`
    }
    if err := json.Unmarshal([]byte(choice.Message.Content), &funcCall); err == nil && funcCall.Name != "" {
        // Это вызов функции в JSON формате
        parts = append(parts, &genai.Part{
            FunctionCall: &genai.FunctionCall{
                Name: funcCall.Name,
                Args: funcCall.Arguments,
            },
        })
    } else {
        // Обычный текст
        parts = append(parts, &genai.Part{Text: choice.Message.Content})
    }
}
```

### Проблема 3: Модель зацикливается на одной функции

**Симптомы:**
```
🔧 Вызов функции: GetDatabaseSchema (вызов #1)
✅ Результат функции GetDatabaseSchema: ...
🔧 Вызов функции: GetDatabaseSchema (вызов #2)
✅ Результат функции GetDatabaseSchema: ...
🔧 Вызов функции: GetDatabaseSchema (вызов #3)
...
```

**Причина:** ADK не передаёт результаты функций обратно в контекст модели.

**Решение - обработка истории:**

```go
// В llm_clients.go - GenerateContent
for _, content := range req.Contents {
    var text string
    var hasFunctionCall bool
    var hasFunctionResponse bool
    
    for _, part := range content.Parts {
        if part.Text != "" {
            text += part.Text
        }
        if part.FunctionCall != nil {
            hasFunctionCall = true
            // Добавляем вызов функции в формате JSON
            funcCallJSON := map[string]interface{}{
                "name":      part.FunctionCall.Name,
                "arguments": part.FunctionCall.Args,
            }
            callJSON, _ := json.Marshal(funcCallJSON)
            text += string(callJSON)
        }
        if part.FunctionResponse != nil {
            hasFunctionResponse = true
            // Добавляем результат с подсказкой для модели
            respJSON, _ := json.Marshal(part.FunctionResponse.Response)
            text += fmt.Sprintf("\nРезультат выполнения функции %s: %s\nТеперь вызови следующую функцию в JSON формате.", 
                part.FunctionResponse.Name, string(respJSON))
        }
    }
    
    if text != "" {
        // Правильно определяем роли сообщений
        if content.Role == genai.RoleUser || hasFunctionResponse {
            messages = append(messages, openai.UserMessage(text))
        } else if content.Role == genai.RoleModel || hasFunctionCall {
            messages = append(messages, openai.AssistantMessage(text))
        }
    }
}
```

**Дополнительная защита - счётчик вызовов:**

```go
// В main.go
callCount := make(map[string]int)
maxCallsPerFunction := 5

if p.FunctionCall != nil {
    funcName := p.FunctionCall.Name
    callCount[funcName]++
    
    if callCount[funcName] > maxCallsPerFunction {
        fmt.Printf("\n⚠️  ВНИМАНИЕ: Функция %s вызывается слишком часто! Останавливаем агента.\n", funcName)
        return false
    }
}
```

### Проблема 4: "Operation not allowed" от OpenRouter

**Симптомы:**
```
{"error": {"type": "llm_call_failed", "message": "{\"message\":\"Operation not allowed\"}\n"}}
```

**Причины:**
1. Модель не поддерживает параметр `tools` в API
2. Неправильный формат запроса
3. Проблемы с API ключом или лимитами

**Решение:**
- Убрать передачу `tools` в параметрах API (ADK добавляет их автоматически)
- Описать tools в системном промпте вместо API параметров
- Проверить баланс и права API ключа

### Проблема 5: Модель возвращает несколько вызовов функций сразу

**Симптомы:**
```
{"name": "GetTableSample", "arguments": {"table_name": "diagnoses"}}
{"name": "GetTableSample", "arguments": {"table_name": "patients"}}
{"name": "GetTableSample", "arguments": {"table_name": "prescriptions"}}
```

**Решение - улучшение промпта:**

```go
КРИТИЧЕСКИ ВАЖНО:
- Вызывай ТОЛЬКО ОДНУ функцию за раз
- Жди результата функции перед следующим вызовом
- Отвечай ТОЛЬКО JSON объектом, БЕЗ дополнительного текста
- НЕ вызывай несколько функций в одном ответе

ПРАВИЛА:
- Каждый ответ = ОДИН JSON вызов функции
- НЕ пиши несколько JSON объектов подряд
- Жди результата перед следующим вызовом
```

---

## Пошаговая реализация

### Шаг 1: Настройка конфигурации

```go
// internal/config.go
type Config struct {
    Qwen     QwenModelConfig
    Database DatabaseConfig
}

type DatabaseConfig struct {
    Type     string // postgres, mysql
    Host     string
    Port     string
    User     string
    Password string
    Name     string
}

func MustLoad(envPath string) Config {
    viper.SetConfigFile(envPath)
    viper.AutomaticEnv()
    
    if err := viper.ReadInConfig(); err != nil {
        panic(err)
    }
    
    // Загружаем конфиг с валидацией
    cfg := Config{...}
    
    if err := cfg.Validate(); err != nil {
        panic(err)
    }
    
    return cfg
}
```

**Файл .env:**
```env
QWEN_MODEL=qwen/qwen3-coder-30b-a3b-instruct
QWEN_API_KEY=sk-or-v1-...
QWEN_BASE_URL=https://openrouter.ai/api/v1

DB_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=meduser
DB_PASSWORD=medpass123
DB_NAME=medical_db
```

### Шаг 2: Реализация LLM клиента

```go
// internal/llm_clients.go
type QwenModel struct {
    client openai.Client
    config QwenModelConfig
}

func NewQwenOpenAIModel(cfg QwenModelConfig) *QwenModel {
    opts := []option.RequestOption{
        option.WithAPIKey(cfg.APIKey),
    }
    if cfg.BaseURL != "" {
        opts = append(opts, option.WithBaseURL(cfg.BaseURL))
    }
    
    client := openai.NewClient(opts...)
    
    return &QwenModel{
        client: client,
        config: cfg,
    }
}

func (m *QwenModel) GenerateContent(ctx context.Context, req *model.LLMRequest, stream bool) iter.Seq2[*model.LLMResponse, error] {
    // 1. Собираем системный промпт
    messages := []openai.ChatCompletionMessageParamUnion{}
    
    if req.Config != nil && req.Config.SystemInstruction != nil {
        var sysText string
        for _, part := range req.Config.SystemInstruction.Parts {
            if part.Text != "" {
                sysText += part.Text
            }
        }
        if sysText != "" {
            messages = append(messages, openai.SystemMessage(sysText))
        }
    }
    
    // 2. Обрабатываем историю (включая FunctionCalls и FunctionResponses)
    for _, content := range req.Contents {
        var text string
        var hasFunctionCall bool
        var hasFunctionResponse bool
        
        for _, part := range content.Parts {
            if part.Text != "" {
                text += part.Text
            }
            if part.FunctionCall != nil {
                hasFunctionCall = true
                funcCallJSON := map[string]interface{}{
                    "name":      part.FunctionCall.Name,
                    "arguments": part.FunctionCall.Args,
                }
                callJSON, _ := json.Marshal(funcCallJSON)
                text += string(callJSON)
            }
            if part.FunctionResponse != nil {
                hasFunctionResponse = true
                respJSON, _ := json.Marshal(part.FunctionResponse.Response)
                text += fmt.Sprintf("\nРезультат выполнения функции %s: %s\nТеперь вызови следующую функцию в JSON формате.", 
                    part.FunctionResponse.Name, string(respJSON))
            }
        }
        
        if text != "" {
            if content.Role == genai.RoleUser || hasFunctionResponse {
                messages = append(messages, openai.UserMessage(text))
            } else if content.Role == genai.RoleModel || hasFunctionCall {
                messages = append(messages, openai.AssistantMessage(text))
            }
        }
    }
    
    // 3. Отправляем запрос
    params := openai.ChatCompletionNewParams{
        Model:    shared.ChatModel(m.config.Model),
        Messages: messages,
    }
    
    resp, err := m.client.Chat.Completions.New(ctx, params)
    if err != nil {
        return func(yield func(*model.LLMResponse, error) bool) {
            yield(nil, err)
        }
    }
    
    // 4. Парсим ответ (JSON из текста или нативный tool call)
    return func(yield func(*model.LLMResponse, error) bool) {
        if len(resp.Choices) == 0 {
            yield(nil, fmt.Errorf("no choices in response"))
            return
        }
        
        choice := resp.Choices[0]
        parts := []*genai.Part{}
        
        // Проверяем нативный tool calling
        if len(choice.Message.ToolCalls) > 0 {
            for _, tc := range choice.Message.ToolCalls {
                var args map[string]interface{}
                json.Unmarshal([]byte(tc.Function.Arguments), &args)
                
                parts = append(parts, &genai.Part{
                    FunctionCall: &genai.FunctionCall{
                        Name: tc.Function.Name,
                        Args: args,
                    },
                })
            }
        } else if choice.Message.Content != "" {
            // Пытаемся распарсить как JSON function call
            var funcCall struct {
                Name      string                 `json:"name"`
                Arguments map[string]interface{} `json:"arguments"`
            }
            if err := json.Unmarshal([]byte(choice.Message.Content), &funcCall); err == nil && funcCall.Name != "" {
                parts = append(parts, &genai.Part{
                    FunctionCall: &genai.FunctionCall{
                        Name: funcCall.Name,
                        Args: funcCall.Arguments,
                    },
                })
            } else {
                // Обычный текст
                parts = append(parts, &genai.Part{Text: choice.Message.Content})
            }
        }
        
        if len(parts) == 0 {
            parts = append(parts, &genai.Part{Text: ""})
        }
        
        yield(&model.LLMResponse{
            Content: &genai.Content{
                Parts: parts,
                Role:  genai.RoleModel,
            },
            TurnComplete: true,
        }, nil)
    }
}
```

### Шаг 3: Создание инструментов (Tools)

```go
// internal/tools.go

// 1. Прямое подключение к БД (без tool.Context)
func ConnectDatabaseDirect(dbType, host, port, user, password, name string) error {
    if dbConnection != nil {
        return nil // уже подключено
    }
    
    var dsn string
    var driverName string
    
    switch dbType {
    case "postgres":
        driverName = "postgres"
        dsn = fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
            host, port, user, password, name)
    case "mysql":
        driverName = "mysql"
        dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true",
            user, password, host, port, name)
    default:
        return fmt.Errorf("неподдерживаемый тип базы данных: %s", dbType)
    }
    
    db, err := sql.Open(driverName, dsn)
    if err != nil {
        return err
    }
    
    if err := db.Ping(); err != nil {
        db.Close()
        return err
    }
    
    db.SetMaxOpenConns(10)
    db.SetMaxIdleConns(5)
    
    dbConnection = db
    currentDBType = dbType
    
    return nil
}

// 2. Tool для получения схемы
type GetDatabaseSchemaArgs struct {}

type GetDatabaseSchemaResult struct {
    Schema string `json:"schema"`
}

func GetDatabaseSchema(ctx tool.Context, args GetDatabaseSchemaArgs) (GetDatabaseSchemaResult, error) {
    if dbConnection == nil {
        return GetDatabaseSchemaResult{}, errors.New("нет подключения к базе данных")
    }
    
    var query string
    switch currentDBType {
    case "postgres":
        query = `
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            ORDER BY table_name, ordinal_position`
    case "mysql":
        query = `
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            ORDER BY table_name, ordinal_position`
    }
    
    rows, err := dbConnection.QueryContext(ctx, query)
    if err != nil {
        return GetDatabaseSchemaResult{}, err
    }
    defer rows.Close()
    
    // Форматируем вывод
    result := strings.Builder{}
    result.WriteString("Схема базы данных:\n\n")
    
    currentTable := ""
    for rows.Next() {
        var tableName, columnName, dataType string
        rows.Scan(&tableName, &columnName, &dataType)
        
        if tableName != currentTable {
            if currentTable != "" {
                result.WriteString("\n")
            }
            result.WriteString(fmt.Sprintf("Таблица: %s\n", tableName))
            currentTable = tableName
        }
        result.WriteString(fmt.Sprintf("  - %s (%s)\n", columnName, dataType))
    }
    
    return GetDatabaseSchemaResult{Schema: result.String()}, nil
}

func NewGetDatabaseSchemaTool() (tool.Tool, error) {
    return functiontool.New(functiontool.Config{
        Name:        "GetDatabaseSchema",
        Description: `Retrieves complete database schema with all tables and their column definitions.`,
    }, GetDatabaseSchema)
}

// 3. Tool для просмотра данных
type GetTableSampleArgs struct {
    TableName string `json:"table_name"`
}

type GetTableSampleResult struct {
    Sample string `json:"sample"`
}

func GetTableSample(ctx tool.Context, args GetTableSampleArgs) (GetTableSampleResult, error) {
    if dbConnection == nil {
        return GetTableSampleResult{}, errors.New("нет подключения к базе данных")
    }
    
    query := fmt.Sprintf("SELECT * FROM %s LIMIT 10", args.TableName)
    rows, err := dbConnection.QueryContext(ctx, query)
    if err != nil {
        return GetTableSampleResult{}, err
    }
    defer rows.Close()
    
    columns, _ := rows.Columns()
    
    result := strings.Builder{}
    result.WriteString(fmt.Sprintf("Первые 10 строк из таблицы %s:\n\n", args.TableName))
    result.WriteString("Колонки: " + strings.Join(columns, ", ") + "\n\n")
    
    rowNum := 0
    for rows.Next() {
        rowNum++
        values := make([]interface{}, len(columns))
        valuePtrs := make([]interface{}, len(columns))
        for i := range values {
            valuePtrs[i] = &values[i]
        }
        
        rows.Scan(valuePtrs...)
        
        result.WriteString(fmt.Sprintf("Строка %d: ", rowNum))
        for i, val := range values {
            if i > 0 {
                result.WriteString(", ")
            }
            result.WriteString(fmt.Sprintf("%s=%v", columns[i], val))
        }
        result.WriteString("\n")
    }
    
    return GetTableSampleResult{Sample: result.String()}, nil
}

// 4. Tool для выполнения запросов
type ExecuteQueryArgs struct {
    Query      string `json:"query"`
    OutputFile string `json:"output_file"`
}

type ExecuteQueryResult struct {
    Message string `json:"message"`
}

func ExecuteQuery(ctx tool.Context, args ExecuteQueryArgs) (ExecuteQueryResult, error) {
    if dbConnection == nil {
        return ExecuteQueryResult{}, errors.New("нет подключения к базе данных")
    }
    
    // Проверка безопасности - только SELECT
    upperQuery := strings.ToUpper(strings.TrimSpace(args.Query))
    if !strings.HasPrefix(upperQuery, "SELECT") {
        return ExecuteQueryResult{}, errors.New("разрешены только SELECT запросы")
    }
    
    rows, err := dbConnection.QueryContext(ctx, args.Query)
    if err != nil {
        return ExecuteQueryResult{}, err
    }
    defer rows.Close()
    
    // Экспорт в CSV
    rowCount, err := ExportToCSV(rows, args.OutputFile)
    if err != nil {
        return ExecuteQueryResult{}, err
    }
    
    return ExecuteQueryResult{
        Message: fmt.Sprintf("Запрос выполнен успешно. Экспортировано %d строк в файл %s", rowCount, args.OutputFile),
    }, nil
}
```

### Шаг 4: Экспорт в CSV с кириллицей

```go
// internal/csv_exporter.go
func ExportToCSV(rows *sql.Rows, filename string) (int, error) {
    file, err := os.Create(filename)
    if err != nil {
        return 0, err
    }
    defer file.Close()
    
    // UTF-8 BOM для корректного отображения кириллицы в Excel
    file.Write([]byte{0xEF, 0xBB, 0xBF})
    
    writer := csv.NewWriter(file)
    defer writer.Flush()
    
    // Получаем названия колонок
    columns, err := rows.Columns()
    if err != nil {
        return 0, err
    }
    
    // Пишем заголовок
    writer.Write(columns)
    
    // Пишем данные
    rowCount := 0
    values := make([]interface{}, len(columns))
    valuePtrs := make([]interface{}, len(columns))
    for i := range values {
        valuePtrs[i] = &values[i]
    }
    
    for rows.Next() {
        err := rows.Scan(valuePtrs...)
        if err != nil {
            return rowCount, err
        }
        
        record := make([]string, len(columns))
        for i, val := range values {
            if val == nil {
                record[i] = ""
            } else {
                record[i] = fmt.Sprintf("%v", val)
            }
        }
        
        writer.Write(record)
        rowCount++
    }
    
    return rowCount, nil
}
```

### Шаг 5: Создание системного промпта

```go
// cmd/main.go
func buildSystemPrompt(dbType string) string {
    return `Ты - специализированный агент для извлечения медицинских данных из баз данных.

КРИТИЧЕСКИ ВАЖНО:
- Вызывай ТОЛЬКО ОДНУ функцию за раз
- Жди результата функции перед следующим вызовом
- Отвечай ТОЛЬКО JSON объектом, БЕЗ дополнительного текста
- НЕ вызывай несколько функций в одном ответе

ДОСТУПНЫЕ ФУНКЦИИ:

1. GetDatabaseSchema - получает схему БД
   Формат: {"name": "GetDatabaseSchema", "arguments": {}}

2. GetTableSample - смотрит данные таблицы  
   Формат: {"name": "GetTableSample", "arguments": {"table_name": "имя_таблицы"}}

3. ExecuteQuery - экспортирует данные в CSV
   Формат: {"name": "ExecuteQuery", "arguments": {"query": "SELECT ...", "output_file": "файл.csv"}}

ПЛАН РАБОТЫ (следуй строго по шагам, вызывай только ОДНУ функцию за раз!):

Шаг 1: Если схема БД ещё не получена -> вызови GetDatabaseSchema
Шаг 2: Если получил схему -> найди таблицы: diagnoses, patients, prescriptions  
Шаг 3: Вызови GetTableSample для ОДНОЙ таблицы, жди результата
Шаг 4: Повтори шаг 3 для остальных таблиц (по одной за раз)
Шаг 5: После просмотра ВСЕХ таблиц -> составь SQL запрос и вызови ExecuteQuery
Шаг 6-7: Экспорт остальных таблиц

ЦЕЛЕВЫЕ ЗАПРОСЫ:
- diagnoses.csv: SELECT code AS код_мкб, diagnosis AS название_диагноза, disease_class AS класс_заболевания FROM diagnoses
- patients.csv: SELECT id, birth_date AS дата_рождения, gender AS пол, district AS район_проживания, region AS регион FROM patients  
- receips.csv: SELECT prescription_date AS дата_рецепта, diagnosis_code AS код_диагноза, drug_code AS код_препарата, patient_id AS id_пациента FROM prescriptions

ПРАВИЛА:
- Каждый ответ = ОДИН JSON вызов функции
- НЕ пиши несколько JSON объектов подряд
- Жди результата перед следующим вызовом
`
}
```

### Шаг 6: Инициализация агента

```go
// cmd/main.go
func main() {
    ctx := context.Background()
    cfg := internal.MustLoad(".env")
    
    // 1. Создаём LLM модель
    llmModel := internal.NewQwenOpenAIModel(cfg.Qwen)
    
    // 2. Подключаемся к БД
    err := internal.ConnectDatabaseDirect(
        cfg.Database.Type, 
        cfg.Database.Host, 
        cfg.Database.Port,
        cfg.Database.User, 
        cfg.Database.Password, 
        cfg.Database.Name,
    )
    if err != nil {
        panic(err)
    }
    defer internal.CloseDBConnection()
    
    // 3. Создаём инструменты
    schemaTool, _ := internal.NewGetDatabaseSchemaTool()
    sampleTool, _ := internal.NewGetTableSampleTool()
    queryTool, _ := internal.NewExecuteQueryTool()
    
    tools := []tool.Tool{
        schemaTool,
        sampleTool,
        queryTool,
    }
    
    // 4. Создаём агента
    systemPrompt := buildSystemPrompt(cfg.Database.Type)
    
    agent, err := llmagent.New(llmagent.Config{
        Name:        "medical-data-agent",
        Model:       llmModel,
        Description: "Агент для извлечения медицинских данных",
        Instruction: systemPrompt,
        Tools:       tools,
    })
    if err != nil {
        panic(err)
    }
    
    // 5. Создаём runner и session
    sessionService := session.InMemoryService()
    r, err := runner.New(runner.Config{
        AppName:        "go-pull-data-agent",
        Agent:          agent,
        SessionService: sessionService,
    })
    
    createResp, _ := sessionService.Create(ctx, &session.CreateRequest{
        AppName: "go-pull-data-agent",
        UserID:  "user-001",
    })
    
    // 6. Запускаем агента
    userMsg := &genai.Content{
        Parts: []*genai.Part{{
            Text: "Проанализируй схему базы данных и экспортируй медицинские данные",
        }},
        Role: genai.RoleUser,
    }
    
    seq := r.Run(ctx, "user-001", createResp.Session.ID(), userMsg, adkagent.RunConfig{})
    
    // 7. Обрабатываем события с защитой от зацикливания
    callCount := make(map[string]int)
    maxCallsPerFunction := 5
    
    seq(func(ev *session.Event, err error) bool {
        if err != nil {
            fmt.Println("❌ Ошибка:", err)
            return false
        }
        if ev == nil {
            return true
        }
        
        if ev.Content != nil {
            for _, p := range ev.Content.Parts {
                if p.FunctionCall != nil {
                    funcName := p.FunctionCall.Name
                    callCount[funcName]++
                    
                    fmt.Printf("🔧 Вызов: %s (#%d)\n", funcName, callCount[funcName])
                    
                    if callCount[funcName] > maxCallsPerFunction {
                        fmt.Println("⚠️ Зацикливание! Останавливаем.")
                        return false
                    }
                }
                
                if p.FunctionResponse != nil {
                    fmt.Printf("✅ Результат: %s\n", p.FunctionResponse.Name)
                }
            }
        }
        
        if ev.IsFinalResponse() {
            fmt.Println("=== Завершено ===")
            return false
        }
        
        return true
    })
}
```

---

## Лучшие практики

### 1. Системный промпт

**✅ Хорошо:**
```go
КРИТИЧЕСКИ ВАЖНО:
- Вызывай ТОЛЬКО ОДНУ функцию за раз
- Отвечай ТОЛЬКО JSON: {"name": "...", "arguments": {...}}
- НЕ пиши текст, код или объяснения

ПЛАН (строго по шагам):
Шаг 1: Вызови FunctionA
Шаг 2: После результата вызови FunctionB
...
```

**❌ Плохо:**
```go
Ты можешь использовать функции для работы с БД.
Попробуй получить схему и данные.
```

### 2. Обработка истории

**✅ Правильно - передавать результаты функций:**
```go
for _, content := range req.Contents {
    for _, part := range content.Parts {
        if part.FunctionResponse != nil {
            respJSON, _ := json.Marshal(part.FunctionResponse.Response)
            text += fmt.Sprintf("Результат: %s\nВызови следующую функцию.", string(respJSON))
        }
    }
}
```

**❌ Неправильно - игнорировать FunctionResponse:**
```go
for _, content := range req.Contents {
    if content.Role == genai.RoleUser {
        // Только текст пользователя, без результатов функций
        messages = append(messages, openai.UserMessage(content.Parts[0].Text))
    }
}
```

### 3. Парсинг ответов модели

**Всегда проверяйте оба варианта:**

1. Нативный OpenAI function calling (`ToolCalls`)
2. JSON в тексте ответа

```go
if len(choice.Message.ToolCalls) > 0 {
    // Вариант 1: Нативный
    ...
} else if choice.Message.Content != "" {
    // Вариант 2: JSON в тексте
    var funcCall struct {
        Name      string                 `json:"name"`
        Arguments map[string]interface{} `json:"arguments"`
    }
    if json.Unmarshal([]byte(choice.Message.Content), &funcCall) == nil {
        // Успешно распарсили
        ...
    }
}
```

### 4. Безопасность

**Всегда валидируйте SQL запросы:**

```go
func ExecuteQuery(ctx tool.Context, args ExecuteQueryArgs) (ExecuteQueryResult, error) {
    upperQuery := strings.ToUpper(strings.TrimSpace(args.Query))
    
    // Разрешаем только SELECT
    if !strings.HasPrefix(upperQuery, "SELECT") {
        return ExecuteQueryResult{}, errors.New("разрешены только SELECT запросы")
    }
    
    // Запрещаем модифицирующие операции
    dangerous := []string{"DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"}
    for _, keyword := range dangerous {
        if strings.Contains(upperQuery, keyword) {
            return ExecuteQueryResult{}, errors.New("запрещены модифицирующие операции")
        }
    }
    
    // Выполняем запрос
    ...
}
```

### 5. CSV с кириллицей

**Обязательно добавляйте UTF-8 BOM:**

```go
file, _ := os.Create(filename)
// UTF-8 BOM для Excel
file.Write([]byte{0xEF, 0xBB, 0xBF})

writer := csv.NewWriter(file)
// ... запись данных
```

### 6. Логирование и отладка

**Используйте DEBUG флаги:**

```go
const DEBUG = true // или из env

if DEBUG {
    fmt.Printf("[DEBUG] Model response: %s\n", choice.Message.Content)
    fmt.Printf("[DEBUG] ToolCalls: %d\n", len(choice.Message.ToolCalls))
}
```

**Выводите прогресс для пользователя:**

```go
if p.FunctionCall != nil {
    fmt.Printf("🔧 Вызов функции: %s\n", p.FunctionCall.Name)
    fmt.Printf("   Аргументы: %v\n", p.FunctionCall.Args)
}

if p.FunctionResponse != nil {
    fmt.Printf("✅ Результат функции %s\n", p.FunctionResponse.Name)
    // Краткий вывод результата (не весь)
}
```

---

## Отладка и тестирование

### Проблема: Модель не вызывает функции

**Диагностика:**

1. Проверьте системный промпт:
```bash
# Добавьте вывод промпта
fmt.Println("=== System Prompt ===")
fmt.Println(systemPrompt)
fmt.Println("=== End ===")
```

2. Проверьте ответ модели:
```go
fmt.Printf("[DEBUG] Model response content: %q\n", choice.Message.Content)
fmt.Printf("[DEBUG] ToolCalls count: %d\n", len(choice.Message.ToolCalls))
```

3. Проверьте, что tools передаются в ADK:
```go
fmt.Printf("[DEBUG] Tools count: %d\n", len(tools))
for _, t := range tools {
    fmt.Printf("[DEBUG] Tool: %s\n", t.Name())
}
```

### Проблема: Зацикливание

**Диагностика:**

```go
callCount := make(map[string]int)

if p.FunctionCall != nil {
    callCount[p.FunctionCall.Name]++
    fmt.Printf("🔧 %s (вызов #%d)\n", p.FunctionCall.Name, callCount[p.FunctionCall.Name])
    
    if callCount[p.FunctionCall.Name] > 3 {
        fmt.Println("⚠️ Возможное зацикливание!")
        // Выведите последние сообщения в контексте
        fmt.Println("История:")
        for i, content := range req.Contents {
            fmt.Printf("  [%d] Role: %s\n", i, content.Role)
        }
    }
}
```

### Проблема: Кодировка в CSV

**Тест:**

```powershell
# PowerShell
Get-Content diagnoses.csv -Encoding UTF8 -First 5

# Должны видеть кириллицу корректно
```

**Если кириллица отображается неправильно:**

1. Проверьте BOM:
```go
file.Write([]byte{0xEF, 0xBB, 0xBF}) // ОБЯЗАТЕЛЬНО для Excel
```

2. Проверьте, что данные приходят в UTF-8:
```sql
-- PostgreSQL
SHOW client_encoding; -- должно быть UTF8
```

### Тестовые кейсы

```go
// test_agent.go
func TestAgentFlow(t *testing.T) {
    // 1. Тест подключения
    err := ConnectDatabaseDirect("postgres", "localhost", "5432", "user", "pass", "db")
    assert.NoError(t, err)
    
    // 2. Тест получения схемы
    schema, err := GetDatabaseSchema(ctx, GetDatabaseSchemaArgs{})
    assert.NoError(t, err)
    assert.Contains(t, schema.Schema, "Таблица:")
    
    // 3. Тест получения примера
    sample, err := GetTableSample(ctx, GetTableSampleArgs{TableName: "patients"})
    assert.NoError(t, err)
    assert.Contains(t, sample.Sample, "Строка 1:")
    
    // 4. Тест экспорта
    result, err := ExecuteQuery(ctx, ExecuteQueryArgs{
        Query:      "SELECT * FROM patients LIMIT 5",
        OutputFile: "test.csv",
    })
    assert.NoError(t, err)
    assert.Contains(t, result.Message, "успешно")
    
    // 5. Проверка файла
    content, _ := os.ReadFile("test.csv")
    assert.True(t, bytes.HasPrefix(content, []byte{0xEF, 0xBB, 0xBF})) // UTF-8 BOM
}
```

---

## Заключение

### Ключевые уроки

1. **LLM ≠ OpenAI API** - разные провайдеры могут не поддерживать все фичи OpenAI API
2. **Промпт критичен** - явные инструкции и примеры обязательны
3. **История важна** - модель должна видеть результаты своих действий
4. **Защита от зацикливания** - всегда добавляйте счётчики и таймауты
5. **UTF-8 + BOM** - для кириллицы в Excel обязательно

### Следующие шаги

- Добавить streaming для больших запросов
- Реализовать кэширование схемы БД
- Добавить retry logic для API вызовов
- Расширить валидацию SQL запросов
- Добавить мониторинг и метрики

### Полезные ссылки

- [Google ADK Documentation](https://pkg.go.dev/google.golang.org/adk)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [PostgreSQL Information Schema](https://www.postgresql.org/docs/current/information-schema.html)

---

**Версия:** 1.0  
**Дата:** 03.12.2025  
**Автор:** Based on practical implementation experience
