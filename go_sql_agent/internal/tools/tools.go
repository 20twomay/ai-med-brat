package tools

import (
	"errors"
	"fmt"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	_ "github.com/lib/pq"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
)

// ===========================
// ExecuteQuery выполняет SQL запрос и сохраняет результаты в CSV
// ===========================

type ExecuteQueryArgs struct {
	Query      string `json:"query"`       // SQL запрос SELECT для выполнения
	OutputFile string `json:"output_file"` // Имя файла для сохранения результатов (например: diagnoses.csv, patients.csv, receips.csv)
}

type ExecuteQueryResult struct {
	Message string `json:"message"` // Сообщение о результате выполнения запроса
}

func ExecuteQuery(ctx tool.Context, args ExecuteQueryArgs) (ExecuteQueryResult, error) {
	if dbConnection == nil {
		return ExecuteQueryResult{}, errors.New("нет подключения к базе данных")
	}

	upperQuery := strings.ToUpper(strings.TrimSpace(args.Query))
	if !strings.HasPrefix(upperQuery, "SELECT") {
		return ExecuteQueryResult{}, errors.New("разрешены только SELECT запросы")
	}
	if strings.Contains(upperQuery, "DROP") || strings.Contains(upperQuery, "DELETE") ||
		strings.Contains(upperQuery, "UPDATE") || strings.Contains(upperQuery, "INSERT") {
		return ExecuteQueryResult{}, errors.New("запрещены модифицирующие операции")
	}

	rows, err := dbConnection.QueryContext(ctx, args.Query)
	if err != nil {
		return ExecuteQueryResult{}, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}
	defer rows.Close()

	rowCount, err := ExportToCSV(rows, args.OutputFile)
	if err != nil {
		return ExecuteQueryResult{}, fmt.Errorf("ошибка экспорта в CSV: %w", err)
	}

	return ExecuteQueryResult{Message: fmt.Sprintf("Запрос выполнен успешно. Экспортировано %d строк в файл %s", rowCount, args.OutputFile)}, nil
}

func NewExecuteQueryTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name: "ExecuteQuery",
		Description: `Executes SELECT SQL queries and exports results to CSV files for data analysis.

REQUIRED: Use this tool when you need to extract specific data from database and save it for further processing.

The tool will:
- Validate query is SELECT-only (no modifications allowed)
- Execute SQL query against connected database
- Export all result rows to specified CSV file
- Return row count and confirmation message

Input: ExecuteQueryArgs with SQL query and output_file name (e.g., diagnoses.csv, patients.csv, receips.csv)
Output: ExecuteQueryResult with success message and number of rows exported`,
	}, ExecuteQuery)
}

