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
// GetDatabaseSchema получает схему базы данных
// ===========================

type GetDatabaseSchemaArgs struct {
}

type GetDatabaseSchemaResult struct {
	Schema string `json:"schema"` // Схема базы данных
}

func GetDatabaseSchema(ctx tool.Context, args GetDatabaseSchemaArgs) (GetDatabaseSchemaResult, error) {
	if dbConnection == nil {
		return GetDatabaseSchemaResult{}, errors.New("нет подключения к базе данных. Сначала используйте connect_database")
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
	default:
		return GetDatabaseSchemaResult{}, errors.New("неподдерживаемый тип базы данных")
	}

	rows, err := dbConnection.QueryContext(ctx, query)
	if err != nil {
		return GetDatabaseSchemaResult{}, fmt.Errorf("ошибка выполнения запроса схемы: %w", err)
	}
	defer rows.Close()

	type columnInfo struct {
		TableName  string
		ColumnName string
		DataType   string
	}

	var columns []columnInfo
	for rows.Next() {
		var col columnInfo
		if err := rows.Scan(&col.TableName, &col.ColumnName, &col.DataType); err != nil {
			return GetDatabaseSchemaResult{}, fmt.Errorf("ошибка чтения данных схемы: %w", err)
		}
		columns = append(columns, col)
	}

	// Форматируем вывод по таблицам
	result := strings.Builder{}
	result.WriteString("Схема базы данных:\n\n")

	currentTable := ""
	for _, col := range columns {
		if col.TableName != currentTable {
			if currentTable != "" {
				result.WriteString("\n")
			}
			result.WriteString(fmt.Sprintf("Таблица: %s\n", col.TableName))
			currentTable = col.TableName
		}
		result.WriteString(fmt.Sprintf("  - %s (%s)\n", col.ColumnName, col.DataType))
	}

	return GetDatabaseSchemaResult{Schema: result.String()}, nil
}

func NewGetDatabaseSchemaTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name: "GetDatabaseSchema",
		Description: `Retrieves complete database schema with all tables and their column definitions.

REQUIRED: Use this tool when you need to understand database structure before writing queries.

The tool will:
- Query information_schema for all tables in the current database
- Extract column names and data types
- Format output grouped by table
- Return human-readable schema description

Input: GetDatabaseSchemaArgs (no parameters required)
Output: GetDatabaseSchemaResult with formatted schema showing tables and columns with data types`,
	}, GetDatabaseSchema)
}