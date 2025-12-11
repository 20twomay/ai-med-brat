package agent

import (
	"context"
	"fmt"

	adkagent "google.golang.org/adk/agent"
	"google.golang.org/adk/agent/llmagent"
	"google.golang.org/adk/runner"
	"google.golang.org/adk/session"
	"google.golang.org/adk/tool"
	"google.golang.org/genai"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/client"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/config"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/logger"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/tokenizer"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/tools"
)

const (
	AgentName        = "medical-data-agent"
	AgentDescription = "Агент для извлечения медицинских данных из базы данных и экспорта в CSV формат"
	AppName          = "go-pull-data-agent"
	UserId           = "local-user"
	DefaultPrompt    = `Проанализируй схему базы данных и экспортируй медицинские данные в три CSV файла:
1. diagnoses.csv - данные о диагнозах
2. patients.csv - данные о пациентах
3. receips.csv - данные о рецептах

Начни с вызова GetDatabaseSchema.`
)

// RunConfig конфигурация для запуска агента
type RunConfig struct {
	ConfigPath  string
	Prompt      string
	MaxAttempts int
	Verbose     bool
}

// Run запускает агента с заданной конфигурацией
func Run(ctx context.Context, runCfg RunConfig) error {
	// Загружаем конфигурацию
	ctx = logger.WithStage(ctx, "Загрузка конфигурации")
	cfg := config.MustLoad(runCfg.ConfigPath)
	logger.Success(ctx, "Конфигурация загружена из %s", runCfg.ConfigPath)
	
	// Инициализируем логгер
	loggerCfg := cfg.LoggerConfig()
	if runCfg.Verbose {
		loggerCfg.Level = logger.DEBUG
	}
	logger.Init(loggerCfg)
	log := logger.GetLogger()
	
	ctx = logger.WithStage(ctx, "Запуск агента")
	log.Debug(ctx, "Конфигурация логгера: Level=%s, ShowTime=%v", cfg.Logger.Level, cfg.Logger.ShowTime)

	// Инициализируем токенизатор
	ctx = logger.WithStage(ctx, "Инициализация токенизатора")
	tokenizerCfg := tokenizer.Config{
		Enabled:         cfg.Tokenizer.Enabled,
		SensitiveFields: cfg.Tokenizer.SensitiveFields,
		UseHashing:      false,
	}
	tokenizer.Init(tokenizerCfg)

	if cfg.Tokenizer.Enabled {
		logger.Success(ctx, "Токенизатор включен - конфиденциальные данные будут маскироваться")
		log.Info(ctx, "LLM будет видеть токены вместо реальных данных")
		log.Info(ctx, "CSV файлы будут содержать реальные (детокенизированные) данные")
	} else {
		log.Warn(ctx, "Токенизатор отключен - данные отправляются в LLM без маскирования")
	}

	// Инициализация LLM модели
	ctx = logger.WithStage(ctx, "Инициализация LLM")
	log.Info(ctx, "Используем Qwen через OpenRouter")
	log.Debug(ctx, "Модель: %s", cfg.Qwen.Model)
	log.Debug(ctx, "Base URL: %s", cfg.Qwen.BaseURL)
	llmModel := client.NewQwenOpenAIModel(cfg.Qwen)
	logger.Success(ctx, "LLM модель инициализирована")

	// Подключаемся к базе данных
	ctx = logger.WithStage(ctx, "Подключение к БД")
	log.Info(ctx, "Подключаемся по адресу %s:%s", cfg.Database.Host, cfg.Database.Port)
	log.Debug(ctx, "База данных: %s (тип: %s)", cfg.Database.Name, cfg.Database.Type)

	err, closeDB := tools.ConnectDatabaseDirect(cfg.Database)
	if err != nil {
		return fmt.Errorf("ошибка подключения к БД: %w", err)
	}
	defer closeDB()
	logger.Success(ctx, "Подключено к базе данных %s, тип %s", cfg.Database.Name, cfg.Database.Type)

	// Создаем инструменты
	ctx = logger.WithStage(ctx, "Инициализация инструментов")
	log.Info(ctx, "Создание инструментов для работы с БД")

	schemaTool, err := tools.NewGetDatabaseSchemaTool()
	if err != nil {
		return fmt.Errorf("ошибка создания GetDatabaseSchemaTool: %w", err)
	}
	log.Debug(ctx, "✓ GetDatabaseSchemaTool создан")

	sampleTool, err := tools.NewGetTableSampleTool()
	if err != nil {
		return fmt.Errorf("ошибка создания GetTableSampleTool: %w", err)
	}
	log.Debug(ctx, "✓ GetTableSampleTool создан")

	queryTool, err := tools.NewExecuteQueryTool()
	if err != nil {
		return fmt.Errorf("ошибка создания ExecuteQueryTool: %w", err)
	}
	log.Debug(ctx, "✓ ExecuteQueryTool создан")

	agentTools := []tool.Tool{
		schemaTool,
		sampleTool,
		queryTool,
	}
	logger.Success(ctx, "Все инструменты (%d шт.) успешно инициализированы", len(agentTools))

	// Создание агента
	ctx = logger.WithStage(ctx, "Создание агента")
	systemPrompt := buildSystemPrompt(string(cfg.Database.Type))
	log.Debug(ctx, "System prompt построен для БД типа: %s", cfg.Database.Type)

	agent, err := llmagent.New(llmagent.Config{
		Name:        AgentName,
		Model:       llmModel,
		Description: AgentDescription,
		Instruction: systemPrompt,
		Tools:       agentTools,
	})
	if err != nil {
		return fmt.Errorf("ошибка создания агента: %w", err)
	}
	logger.Success(ctx, "Агент создан: %s", AgentName)

	// Создание runner и session
	ctx = logger.WithStage(ctx, "Инициализация сессии")
	sessionService := session.InMemoryService()
	r, err := runner.New(runner.Config{
		AppName:        AppName,
		Agent:          agent,
		SessionService: sessionService,
	})
	if err != nil {
		return fmt.Errorf("ошибка создания runner: %w", err)
	}
	log.Debug(ctx, "Runner создан для приложения: %s", AppName)

	createResp, err := sessionService.Create(ctx, &session.CreateRequest{
		AppName: AppName,
		UserID:  UserId,
	})
	if err != nil {
		return fmt.Errorf("ошибка создания сессии: %w", err)
	}

	sessionID := createResp.Session.ID()
	logger.Success(ctx, "Сессия создана для пользователя: %s (ID: %s)", UserId, sessionID)

	// Запуск агента
	prompt := runCfg.Prompt
	if prompt == "" {
		prompt = DefaultPrompt
	}

	ctx = logger.WithStage(ctx, "Запуск агента")
	log.Info(ctx, "Отправка задачи агенту")
	log.Debug(ctx, "Промпт: %s", prompt)

	userMsg := &genai.Content{
		Parts: []*genai.Part{{Text: prompt}},
		Role:  genai.RoleUser,
	}

	seq := r.Run(ctx, UserId, sessionID, userMsg, adkagent.RunConfig{})
	logger.Success(ctx, "Агент запущен, начинаем обработку событий")

	maxCallsPerFunction := runCfg.MaxAttempts

	callCount := make(map[string]int)

	// Создаём контекст для обработки событий
	eventCtx := logger.WithStage(ctx, "Обработка событий")
	
	seq(func(ev *session.Event, err error) bool {
		if err != nil {
			log.Error(eventCtx, "Ошибка при обработке события: %v", err)
			return false
		}
		if ev == nil {
			return true
		}

		if ev.Content != nil {
			for _, p := range ev.Content.Parts {
				if p != nil {
					if p.Text != "" {
						fmt.Print(p.Text)
					}
					if p.FunctionCall != nil {
						funcName := p.FunctionCall.Name
						callCount[funcName]++

						log.Info(eventCtx, "Вызов функции: %s (вызов #%d)", funcName, callCount[funcName])
						log.Debug(eventCtx, "   Аргументы: %v", p.FunctionCall.Args)

						if callCount[funcName] > maxCallsPerFunction {
							log.Warn(eventCtx, "Функция %s вызывается слишком часто! Останавливаем агента.", funcName)
							return false
						}
					}
					if p.FunctionResponse != nil {
						log.Info(eventCtx, "Результат получен от функции: %s", p.FunctionResponse.Name)
					}
				}
			}
		}

		if ev.IsFinalResponse() {
			fmt.Println()
			finalCtx := logger.WithStage(context.Background(), "Завершение")
			logger.Success(finalCtx, "Все задачи выполнены")

			if tokenizer.GetTokenizer().IsEnabled() {
				stats := tokenizer.GetTokenizer().GetStats()
				
				statsCtx := logger.WithStage(context.Background(), "Статистика")
				log.Info(statsCtx, "Всего токенизировано значений: %v", stats["total_tokens"])
				log.Info(statsCtx, "Типов токенов: %v", stats["token_types"])
				if counters, ok := stats["counters"].(map[tokenizer.TokenType]int); ok {
					for tokenType, count := range counters {
						log.Debug(statsCtx, "  %s: %d значений", tokenType, count)
					}
				}
				log.Info(statsCtx, "Все конфиденциальные данные были защищены от LLM")
			}

			return false
		}

		return true
	})

	return nil
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