package main

import (
	"context"
	"flag"
	"fmt"

	adkagent "google.golang.org/adk/agent"
	"google.golang.org/adk/agent/llmagent"
	"google.golang.org/adk/runner"
	"google.golang.org/adk/session"
	"google.golang.org/adk/tool"
	"google.golang.org/genai"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal"

	// Импортируем драйверы БД
	_ "github.com/go-sql-driver/mysql"
	_ "github.com/lib/pq"
)

var cfgPath string

func init() {
	flag.StringVar(&cfgPath, "cfg", ".env", "path to config file")

	flag.Parse()
}

func main() {
	const AppName = "go-pull-data-agent"
	const UserId = "user-001"

	ctx := context.Background()

	cfg := internal.MustLoad(cfgPath)

	// Создаем LLM модель
	fmt.Println("📡 Используем Qwen через OpenRouter")
	llmModel := internal.NewQwenOpenAIModel(cfg.Qwen)

	// Подключаемся к базе данных напрямую через функцию-помощник
	fmt.Println("🔌 Подключаемся к базе данных...")
	err := internal.ConnectDatabaseDirect(cfg.Database.Type, cfg.Database.Host, cfg.Database.Port,
		cfg.Database.User, cfg.Database.Password, cfg.Database.Name)
	if err != nil {
		panic(fmt.Sprintf("Ошибка подключения к БД: %v", err))
	}
	fmt.Printf("✅ Подключено к базе данных %s типа %s\n\n", cfg.Database.Name, cfg.Database.Type)

	// Создаем инструменты для работы с базой данных (без ConnectDatabase)
	schemaTool, err := internal.NewGetDatabaseSchemaTool()
	if err != nil {
		panic(err)
	}
	sampleTool, err := internal.NewGetTableSampleTool()
	if err != nil {
		panic(err)
	}
	queryTool, err := internal.NewExecuteQueryTool()
	if err != nil {
		panic(err)
	}

	tools := []tool.Tool{
		schemaTool,
		sampleTool,
		queryTool,
	}

	defer internal.CloseDBConnection()

	systemPrompt := buildSystemPrompt(cfg.Database.Type)

	agent, err := llmagent.New(llmagent.Config{
		Name:        "medical-data-agent",
		Model:       llmModel,
		Description: "Агент для извлечения медицинских данных из базы данных и экспорта в CSV формат",
		Instruction: systemPrompt,
		Tools:       tools,
	})
	if err != nil {
		panic(err)
	}

	sessionService := session.InMemoryService()
	config := runner.Config{
		AppName:        AppName,
		Agent:          agent,
		SessionService: sessionService,
	}

	r, err := runner.New(config)
	if err != nil {
		panic(err)
	}

	// Create or get session for the user
	createResp, err := sessionService.Create(ctx, &session.CreateRequest{
		AppName: AppName,
		UserID:  UserId,
	})
	if err != nil {
		panic(err)
	}

	sessionID := createResp.Session.ID()

	// Автоматический запрос на извлечение медицинских данных
	prompt := `Проанализируй схему базы данных и экспортируй медицинские данные в три CSV файла:
1. diagnoses.csv - данные о диагнозах
2. patients.csv - данные о пациентах  
3. receips.csv - данные о рецептах

Начни с вызова GetDatabaseSchema.`
	userMsg := &genai.Content{
		Parts: []*genai.Part{{Text: prompt}},
		Role:  genai.RoleUser,
	}

	// Run the agent for this user input and iterate returned events
	seq := r.Run(ctx, UserId, sessionID, userMsg, adkagent.RunConfig{})

	fmt.Println("=== Запуск агента ===")
	fmt.Println()

	callCount := make(map[string]int)
	maxCallsPerFunction := 5 // Увеличиваем лимит

	seq(func(ev *session.Event, err error) bool {
		if err != nil {
			fmt.Println("❌ Ошибка:", err)
			return false
		}
		if ev == nil {
			return true
		}

		// Логирование типа события
		if ev.Author != "" {
			fmt.Printf("\n[%s]: ", ev.Author)
		}

		// Print any content parts (model responses)
		if ev.Content != nil {
			for _, p := range ev.Content.Parts {
				if p != nil {
					if p.Text != "" {
						fmt.Print(p.Text)
					}
					if p.FunctionCall != nil {
						funcName := p.FunctionCall.Name
						callCount[funcName]++

						fmt.Printf("\n🔧 Вызов функции: %s (вызов #%d)", funcName, callCount[funcName])
						fmt.Printf("\n   Аргументы: %v\n", p.FunctionCall.Args)

						// Проверяем зацикливание
						if callCount[funcName] > maxCallsPerFunction {
							fmt.Printf("\n⚠️  ВНИМАНИЕ: Функция %s вызывается слишком часто! Останавливаем агента.\n", funcName)
							return false
						}
					}
					if p.FunctionResponse != nil {
						fmt.Printf("\n✅ Результат функции %s:", p.FunctionResponse.Name)
						// Вывод результата
						for k, v := range p.FunctionResponse.Response {
							// Ограничиваем длину вывода
							vStr := fmt.Sprintf("%v", v)
							if len(vStr) > 500 {
								vStr = vStr[:500] + "... (обрезано)"
							}
							fmt.Printf("\n   %s: %s", k, vStr)
						}
						fmt.Println()
					}
				}
			}
		}

		// Continue unless it's a final response
		if ev.IsFinalResponse() {
			fmt.Println()
			fmt.Println("\n=== Работа агента завершена ===")
			return false
		}

		return true
	})
}

func buildSystemPrompt(dbType string) string {
	basePrompt := `Ты - специализированный агент для извлечения медицинских данных из баз данных.

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
Шаг 5: После просмотра ВСЕХ таблиц -> составь SQL запрос и вызови ExecuteQuery для diagnoses.csv
Шаг 6: Вызови ExecuteQuery для patients.csv
Шаг 7: Вызови ExecuteQuery для receips.csv

ЦЕЛЕВЫЕ ЗАПРОСЫ:
- diagnoses.csv: SELECT code AS код_мкб, diagnosis AS название_диагноза, disease_class AS класс_заболевания FROM diagnoses
- patients.csv: SELECT id, birth_date AS дата_рождения, gender AS пол, district AS район_проживания, region AS регион FROM patients  
- receips.csv: SELECT prescription_date AS дата_рецепта, diagnosis_code AS код_диагноза, drug_code AS код_препарата, patient_id AS id_пациента FROM prescriptions

ПРАВИЛА:
- Каждый ответ = ОДИН JSON вызов функции
- НЕ пиши несколько JSON объектов подряд
- Жди результата перед следующим вызовом
`

	var dbSpecific string
	switch dbType {
	case "postgres":
		dbSpecific = `
База данных: PostgreSQL
Используй стандартный SQL синтаксис для PostgreSQL.
`
	case "mysql":
		dbSpecific = `
База данных: MySQL
Используй стандартный SQL синтаксис для MySQL.
`
	default:
		dbSpecific = ""
	}

	return basePrompt + dbSpecific
}
