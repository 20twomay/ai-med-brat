package tools

import (
	"errors"
	"fmt"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	_ "github.com/lib/pq"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/tokenizer"
)


// ===========================
// GetTableSample получает пример данных из таблицы
// ===========================

type GetTableSampleArgs struct {
	TableName string `json:"table_name"` // Название таблицы для получения примера данных
}

type GetTableSampleResult struct {
	Sample string `json:"sample"` // Пример данных из таблицы
}

func GetTableSample(ctx tool.Context, args GetTableSampleArgs) (GetTableSampleResult, error) {
	if dbConnection == nil {
		return GetTableSampleResult{}, errors.New("нет подключения к базе данных")
	}

	query := fmt.Sprintf("SELECT * FROM %s LIMIT 10", args.TableName)
	rows, err := dbConnection.QueryContext(ctx, query)
	if err != nil {
		return GetTableSampleResult{}, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return GetTableSampleResult{}, fmt.Errorf("ошибка получения колонок: %w", err)
	}

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

		if err := rows.Scan(valuePtrs...); err != nil {
			return GetTableSampleResult{}, fmt.Errorf("ошибка чтения строки: %w", err)
		}

		result.WriteString(fmt.Sprintf("Строка %d: ", rowNum))
		for i, val := range values {
			if i > 0 {
				result.WriteString(", ")
			}

			// Токенизируем значение перед отправкой в LLM
			strVal := fmt.Sprintf("%v", val)
			if val != nil && tokenizer.GetTokenizer().IsEnabled() {
				// Определяем тип токена на основе имени колонки
				tokenType := detectColumnTokenType(columns[i])
				if tokenType != "" {
					strVal = tokenizer.GetTokenizer().Tokenize(strVal, tokenType)
				}
			}

			result.WriteString(fmt.Sprintf("%s=%v", columns[i], strVal))
		}
		result.WriteString("\n")
	}

	return GetTableSampleResult{Sample: result.String()}, nil
}

// detectColumnTokenType определяет тип токена для колонки
func detectColumnTokenType(columnName string) tokenizer.TokenType {
	colLower := strings.ToLower(columnName)

	switch {
	case strings.Contains(colLower, "name") || strings.Contains(colLower, "fio"):
		return tokenizer.TokenTypeName
	case strings.Contains(colLower, "date") || strings.Contains(colLower, "birth"):
		return tokenizer.TokenTypeDate
	case strings.Contains(colLower, "phone") || strings.Contains(colLower, "tel"):
		return tokenizer.TokenTypePhone
	case strings.Contains(colLower, "email"):
		return tokenizer.TokenTypeEmail
	case strings.Contains(colLower, "address") || strings.Contains(colLower, "district") || strings.Contains(colLower, "region"):
		return tokenizer.TokenTypeAddress
	case strings.Contains(colLower, "id"):
		return tokenizer.TokenTypeID
	case strings.Contains(colLower, "diagnosis") || strings.Contains(colLower, "disease"):
		return tokenizer.TokenTypeDiagnosis
	case strings.Contains(colLower, "drug") || strings.Contains(colLower, "medication"):
		return tokenizer.TokenTypeDrug
	default:
		return ""
	}

}

func NewGetTableSampleTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name: "GetTableSample",
		Description: `Retrieves sample data from a specified table to understand its content and structure.

REQUIRED: Use this tool when you need to see actual data examples before constructing queries.

The tool will:
- Execute SELECT query with LIMIT 10
- Retrieve column names from result set
- Format each row with column=value pairs
- Return structured sample output

Input: GetTableSampleArgs with table_name
Output: GetTableSampleResult with first 10 rows showing all columns and their values`,
	}, GetTableSample)
}