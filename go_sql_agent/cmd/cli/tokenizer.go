package cli

import (
	"fmt"

	"github.com/spf13/cobra"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/config"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/tokenizer"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/ui"
)

var tokenizerCmd = &cobra.Command{
	Use:   "tokenizer",
	Short: "Управление токенизацией данных",
	Long:  `Команды для работы с системой токенизации конфиденциальных данных.`,
}

var tokenizerInfoCmd = &cobra.Command{
	Use:   "info",
	Short: "Информация о токенизаторе",
	Long:  `Показывает информацию о настройках и возможностях токенизатора.`,
	Example: `  # Показать информацию
  agent tokenizer info

  # С конкретной конфигурацией
  agent tokenizer info --config production.env`,
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg := config.MustLoad(GetConfigFile())

		ui.Header("Информация о токенизаторе")

		if cfg.Tokenizer.Enabled {
			ui.Success("Токенизация ВКЛЮЧЕНА")
			fmt.Println()
			ui.Info("Защищенные данные:")
			ui.Item("LLM видит только токены вместо реальных значений")
			ui.Item("CSV файлы содержат детокенизированные (реальные) данные")
		} else {
			ui.Warning("Токенизация ОТКЛЮЧЕНА")
			fmt.Println()
			ui.Error("Внимание:")
			ui.Item("Конфиденциальные данные отправляются в LLM без маскирования!")
			ui.Item("Включите токенизацию в .env: TOKENIZER_ENABLED=true")
		}

		ui.Subheader(fmt.Sprintf("Чувствительные поля (%d)", len(cfg.Tokenizer.SensitiveFields)))
		for _, field := range cfg.Tokenizer.SensitiveFields {
			ui.Item(field)
		}

		ui.Subheader("Типы токенов")
		table := &ui.Table{
			Headers: []string{"Префикс", "Описание"},
			Rows: [][]string{
				{"NAME_xxx", "Имена, ФИО"},
				{"DATE_xxx", "Даты рождения"},
				{"ADDR_xxx", "Адреса, районы, регионы"},
				{"PHONE_xxx", "Телефоны"},
				{"EMAIL_xxx", "Email адреса"},
				{"ID_xxx", "Идентификаторы"},
				{"DIAG_xxx", "Диагнозы"},
				{"DRUG_xxx", "Препараты"},
				{"NUM_xxx", "Числовые значения (зарплаты, суммы)"},
			},
		}
		table.Print()

		return nil
	},
}

var tokenizerTestCmd = &cobra.Command{
	Use:   "test [value]",
	Short: "Протестировать токенизацию",
	Long:  `Показывает как будет токенизировано значение.`,
	Example: `  # Протестировать токенизацию имени
  agent tokenizer test "Иванов Петр Сергеевич"

  # Протестировать дату
  agent tokenizer test "1990-05-15"`,
	Args: cobra.MinimumNArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg := config.MustLoad(GetConfigFile())

		if !cfg.Tokenizer.Enabled {
			ui.Warning("Токенизация отключена в конфигурации")
			ui.Info("Установите TOKENIZER_ENABLED=true в .env файле")
			return nil
		}

		// Инициализируем токенизатор
		tok := tokenizer.New(tokenizer.Config{
			Enabled:         cfg.Tokenizer.Enabled,
			SensitiveFields: cfg.Tokenizer.SensitiveFields,
			UseHashing:      false,
		})

		value := args[0]

		ui.Header("Тест токенизации")
		ui.KeyValue("Оригинал", value)

		// Тестируем разные типы токенов
		testTypes := []struct {
			name      string
			tokenType tokenizer.TokenType
		}{
			{"Имя", tokenizer.TokenTypeName},
			{"Дата", tokenizer.TokenTypeDate},
			{"Адрес", tokenizer.TokenTypeAddress},
			{"Телефон", tokenizer.TokenTypePhone},
			{"Email", tokenizer.TokenTypeEmail},
			{"ID", tokenizer.TokenTypeID},
			{"Диагноз", tokenizer.TokenTypeDiagnosis},
			{"Препарат", tokenizer.TokenTypeDrug},
		}

		ui.Subheader("Токенизация по типам")
		for _, tt := range testTypes {
			token := tok.Tokenize(value, tt.tokenType)
			ui.KeyValue(tt.name, token)
		}

		fmt.Println()
		ui.Info("Совет:")
		ui.Item("Тип токена определяется автоматически по имени поля в БД")

		return nil
	},
}

var tokenizerFieldsCmd = &cobra.Command{
	Use:   "fields",
	Short: "Список чувствительных полей",
	Long:  `Показывает список полей, которые будут токенизироваться.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg := config.MustLoad(GetConfigFile())

		ui.Header("Чувствительные поля")

		if len(cfg.Tokenizer.SensitiveFields) == 0 {
			ui.Warning("Список чувствительных полей пуст!")
			return nil
		}

		ui.Info("Всего: %d полей", len(cfg.Tokenizer.SensitiveFields))
		fmt.Println()

		// Группируем по категориям
		categories := map[string][]string{
			"Персональные данные": {},
			"Контакты":            {},
			"Медицинские":         {},
			"Геолокация":          {},
			"Финансы":             {},
			"Прочее":              {},
		}

		for _, field := range cfg.Tokenizer.SensitiveFields {
			switch {
			case contains(field, "name", "fio"):
				categories["Персональные данные"] = append(categories["Персональные данные"], field)
			case contains(field, "phone", "email"):
				categories["Контакты"] = append(categories["Контакты"], field)
			case contains(field, "diagnosis", "disease", "drug", "medication", "prescription"):
				categories["Медицинские"] = append(categories["Медицинские"], field)
			case contains(field, "district", "region", "address"):
				categories["Геолокация"] = append(categories["Геолокация"], field)
			case contains(field, "salary", "income", "account", "card"):
				categories["Финансы"] = append(categories["Финансы"], field)
			default:
				categories["Прочее"] = append(categories["Прочее"], field)
			}
		}

		for category, fields := range categories {
			if len(fields) > 0 {
				ui.Subheader(fmt.Sprintf("%s (%d)", category, len(fields)))
				for _, field := range fields {
					ui.Item(field)
				}
				fmt.Println()
			}
		}

		ui.Info("Подсказка:")
		ui.Item("Эти поля будут автоматически маскироваться при отправке в LLM")
		ui.Item("Настроить список можно через TOKENIZER_SENSITIVE_FIELDS в .env")

		return nil
	},
}

func contains(str string, substrs ...string) bool {
	for _, substr := range substrs {
		if len(str) >= len(substr) && str[:len(substr)] == substr {
			return true
		}
		// Также проверяем вхождение подстроки
		for i := 0; i <= len(str)-len(substr); i++ {
			if str[i:i+len(substr)] == substr {
				return true
			}
		}
	}
	return false
}

func init() {
	rootCmd.AddCommand(tokenizerCmd)
	tokenizerCmd.AddCommand(tokenizerInfoCmd)
	tokenizerCmd.AddCommand(tokenizerTestCmd)
	tokenizerCmd.AddCommand(tokenizerFieldsCmd)
}