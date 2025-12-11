package cli

import (
	"context"

	"github.com/spf13/cobra"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/agent"
	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/ui"
)

var (
	runPrompt      string
	runMaxAttempts int
)

var runCmd = &cobra.Command{
	Use:   "run",
	Short: "Запустить агента для извлечения данных",
	Long: `Запускает агента для автоматического извлечения медицинских данных из БД.

Агент:
  1. Анализирует схему базы данных
  2. Просматривает примеры данных (токенизированные)
  3. Создает SQL запросы
  4. Экспортирует данные в CSV файлы (реальные данные)

По умолчанию экспортируются файлы:
  - diagnoses.csv (диагнозы)
  - patients.csv (пациенты)
  - receips.csv (рецепты)`,
	Example: `  # Запуск с настройками по умолчанию
  agent run

  # Использование кастомного конфигурационного файла
  agent run --config production.env

  # Подробный режим (DEBUG логирование)
  agent run --verbose

  # Кастомный промпт для агента
  agent run --prompt "Экспортируй только данные о пациентах"

  # Увеличить лимит попыток вызова функций
  agent run --max-attempts 10`,
	RunE: func(cmd *cobra.Command, args []string) error {
		// Показываем логотип
		ui.PrintLogo()

		ctx := context.Background()

		runCfg := agent.RunConfig{
			ConfigPath:  GetConfigFile(),
			Prompt:      runPrompt,
			MaxAttempts: runMaxAttempts,
			Verbose:     IsVerbose(),
		}

		if err := agent.Run(ctx, runCfg); err != nil {
			ui.Error("Ошибка запуска агента: %v", err)
			return err
		}

		return nil
	},
}

func init() {
	rootCmd.AddCommand(runCmd)

	runCmd.Flags().StringVarP(&runPrompt, "prompt", "p", "", "кастомный промпт для агента")
	runCmd.Flags().IntVarP(&runMaxAttempts, "max-attempts", "m", 50, "максимальное количество вызовов одной функции")
}