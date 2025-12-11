package cli

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var (
	cfgFile string
	verbose bool
)

// rootCmd представляет базовую команду при вызове без подкоманд
var rootCmd = &cobra.Command{
	Use:   "agent",
	Short: "Медицинский SQL агент для извлечения данных",
	Long: `Агент для автоматического извлечения медицинских данных из баз данных
с использованием LLM и экспорта в CSV формат.

Особенности:
  • Автоматический анализ схемы БД
  • Токенизация конфиденциальных данных
  • Экспорт в CSV с реальными данными
  • Защита данных от утечки в LLM

Примеры:
  agent run                  # Запустить агент с настройками по умолчанию
  agent run --config .env    # Использовать конкретный файл конфигурации
  agent config validate      # Проверить конфигурацию
  agent tokenizer stats      # Показать статистику токенизации`,
}

// Execute добавляет все дочерние команды к корневой команде и устанавливает флаги
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	// Глобальные флаги
	rootCmd.PersistentFlags().StringVarP(&cfgFile, "config", "c", ".env", "файл конфигурации")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "подробный вывод (DEBUG уровень логирования)")
}

// GetConfigFile возвращает путь к файлу конфигурации
func GetConfigFile() string {
	return cfgFile
}

// IsVerbose возвращает флаг подробного вывода
func IsVerbose() bool {
	return verbose
}