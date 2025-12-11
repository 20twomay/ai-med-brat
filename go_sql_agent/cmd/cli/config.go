package cli

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/config"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/ui"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Управление конфигурацией",
	Long:  `Команды для работы с конфигурацией агента.`,
}

var configValidateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Проверить конфигурацию",
	Long:  `Проверяет корректность конфигурационного файла и выводит текущие настройки.`,
	Example: `  # Проверить конфигурацию по умолчанию
  agent config validate

  # Проверить конкретный файл
  agent config validate --config production.env`,
	RunE: func(cmd *cobra.Command, args []string) error {
		cfgPath := GetConfigFile()

		ui.Info("Проверка конфигурации: %s", cfgPath)
		fmt.Println()

		// Проверяем существование файла
		if _, err := os.Stat(cfgPath); os.IsNotExist(err) {
			ui.Error("Файл конфигурации не найден: %s", cfgPath)
			return err
		}

		// Загружаем и валидируем конфигурацию
		cfg := config.MustLoad(cfgPath)

		ui.Success("Конфигурация валидна!")
		fmt.Println()

		// Выводим настройки
		ui.Header("Qwen API")
		ui.KeyValue("Модель", cfg.Qwen.Model)
		ui.KeyValue("Base URL", cfg.Qwen.BaseURL)
		ui.KeyValue("API Key", cfg.Qwen.APIKey[:10]+"***")

		ui.Header("База данных")
		ui.KeyValue("Тип", string(cfg.Database.Type))
		ui.KeyValue("Хост", fmt.Sprintf("%s:%s", cfg.Database.Host, cfg.Database.Port))
		ui.KeyValue("БД", cfg.Database.Name)
		ui.KeyValue("Пользователь", cfg.Database.User)

		ui.Header("Логирование")
		ui.KeyValue("Уровень", cfg.Logger.Level.String())
		ui.KeyValue("Время", fmt.Sprintf("%v", cfg.Logger.ShowTime))

		ui.Header("Токенизация")
		if cfg.Tokenizer.Enabled {
			ui.KeyValue("Статус", "✅ Включена")
			ui.KeyValue("Чувствительных полей", fmt.Sprintf("%d", len(cfg.Tokenizer.SensitiveFields)))
			if len(cfg.Tokenizer.SensitiveFields) > 0 {
				fmt.Println()
				ui.Subheader("Первые 10 полей")
				for i, field := range cfg.Tokenizer.SensitiveFields {
					if i < 10 {
						ui.Item(field)
					}
				}
				if len(cfg.Tokenizer.SensitiveFields) > 10 {
					ui.Item("... и еще %d", len(cfg.Tokenizer.SensitiveFields)-10)
				}
			}
		} else {
			ui.KeyValue("Статус", "⚠️  Отключена")
		}

		return nil
	},
}

var configShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Показать текущую конфигурацию",
	Long:  `Выводит содержимое файла конфигурации.`,
	Example: `  # Показать конфигурацию по умолчанию
  agent config show

  # Показать конкретный файл
  agent config show --config production.env`,
	RunE: func(cmd *cobra.Command, args []string) error {
		cfgPath := GetConfigFile()

		content, err := os.ReadFile(cfgPath)
		if err != nil {
			ui.Error("Ошибка чтения файла: %v", err)
			return err
		}

		ui.Header("Файл: " + cfgPath)
		fmt.Println(string(content))

		return nil
	},
}

var configInitCmd = &cobra.Command{
	Use:   "init",
	Short: "Создать файл конфигурации по умолчанию",
	Long:  `Создает новый файл .env с настройками по умолчанию.`,
	Example: `  # Создать .env файл
  agent config init

  # Создать конфигурацию с другим именем
  agent config init --config custom.env`,
	RunE: func(cmd *cobra.Command, args []string) error {
		cfgPath := GetConfigFile()

		// Проверяем, не существует ли уже файл
		if _, err := os.Stat(cfgPath); err == nil {
			ui.Error("Файл %s уже существует", cfgPath)
			ui.Warning("Удалите его вручную или используйте другое имя")
			return fmt.Errorf("файл уже существует")
		}

		// Создаем файл с настройками по умолчанию
		defaultConfig := `# Qwen API Configuration
QWEN_MODEL=qwen/qwen3-coder-30b-a3b-instruct
QWEN_API_KEY=your_api_key_here
QWEN_BASE_URL=https://api.openai.com/v1

# Database Configuration
DB_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_database_name

# For MySQL use:
# DB_TYPE=mysql
# DB_PORT=3306

# Logger Configuration
# LOG_LEVEL: DEBUG, INFO, WARN, ERROR, FATAL (default: INFO)
LOG_LEVEL=INFO
# LOG_USE_EMOJI: true/false (default: true)
LOG_USE_EMOJI=true
# LOG_SHOW_TIME: true/false (default: true)
LOG_SHOW_TIME=true

# Tokenizer Configuration (Data Masking)
# TOKENIZER_ENABLED: Включить маскирование конфиденциальных данных перед отправкой в LLM
# LLM видит только токены (NAME_001, ADDR_001), но CSV файлы содержат реальные данные
TOKENIZER_ENABLED=true
# TOKENIZER_SENSITIVE_FIELDS: Список полей для маскирования (через запятую)
# По умолчанию: name, phone, email, address, birth_date, diagnosis, drug, district, region
# TOKENIZER_SENSITIVE_FIELDS=name,phone,email,address
`

		if err := os.WriteFile(cfgPath, []byte(defaultConfig), 0644); err != nil {
			ui.Error("Ошибка создания файла: %v", err)
			return err
		}

		ui.Success("Создан файл конфигурации: %s", cfgPath)
		fmt.Println()
		ui.Warning("Не забудьте заполнить следующие поля:")
		ui.Item("QWEN_API_KEY")
		ui.Item("DB_USER")
		ui.Item("DB_PASSWORD")
		ui.Item("DB_NAME")

		return nil
	},
}

func init() {
	rootCmd.AddCommand(configCmd)
	configCmd.AddCommand(configValidateCmd)
	configCmd.AddCommand(configShowCmd)
	configCmd.AddCommand(configInitCmd)
}