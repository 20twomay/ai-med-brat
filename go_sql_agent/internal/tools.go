package internal

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	_ "github.com/lib/pq"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
)

var dbConnection *sql.DB
var currentDBType string

// ===========================
// ConnectDatabase подключается к базе данных
// ===========================

type ConnectDatabaseArgs struct {
	Type     string `json:"type"` // postgres, mysql
	Host     string `json:"host"`
	Port     string `json:"port"`
	User     string `json:"user"`
	Password string `json:"password"`
	Name     string `json:"name"`
}

type ConnectDatabaseResult struct {
	StatusMessage string `json:"status_message"` // Сообщение о результате подключения
}

func ConnectDatabase(ctx tool.Context, config ConnectDatabaseArgs) (ConnectDatabaseResult, error) {
	if dbConnection != nil {
		return ConnectDatabaseResult{StatusMessage: "База данных уже подключена"}, nil
	}

	var dsn string
	var driverName string

	switch config.Type {
	case "postgres":
		driverName = "postgres"
		dsn = fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
			config.Host, config.Port, config.User, config.Password, config.Name)
	case "mysql":
		driverName = "mysql"
		dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true",
			config.User, config.Password, config.Host, config.Port, config.Name)
	default:
		return ConnectDatabaseResult{StatusMessage: fmt.Sprintf("неподдерживаемый тип базы данных: %s", config.Type)}, fmt.Errorf("неподдерживаемый тип базы данных: %s", config.Type)
	}

	db, err := sql.Open(driverName, dsn)
	if err != nil {
		return ConnectDatabaseResult{StatusMessage: fmt.Sprintf("ошибка открытия соединения: %v", err)}, err
	}

	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return ConnectDatabaseResult{StatusMessage: fmt.Sprintf("ошибка подключения к базе данных: %v", err)}, err
	}

	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)

	dbConnection = db
	currentDBType = config.Type

	return ConnectDatabaseResult{StatusMessage: fmt.Sprintf("Успешно подключено к базе данных %s типа %s", config.Name, config.Type)}, err
}

func NewConnectDatabaseTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name: "ConnectDatabase",
		Description: `Establishes connection to a PostgreSQL or MySQL database with specified credentials.

REQUIRED: Use this tool before any database operations when connection is not yet established.

The tool will:
- Validate database type (postgres or mysql)
- Build appropriate connection string
- Test connection with ping
- Configure connection pool settings
- Store connection for subsequent operations

Input: ConnectDatabaseArgs with type, host, port, user, password, and database name
Output: ConnectDatabaseResult with status message confirming successful connection`,
	}, ConnectDatabase)
}

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
			result.WriteString(fmt.Sprintf("%s=%v", columns[i], val))
		}
		result.WriteString("\n")
	}

	return GetTableSampleResult{Sample: result.String()}, nil
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

// ===========================
// Helpers
// ===========================

// ConnectDatabaseDirect подключается к БД напрямую без tool.Context
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
		return fmt.Errorf("ошибка открытия соединения: %w", err)
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return fmt.Errorf("ошибка подключения к базе данных: %w", err)
	}

	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)

	dbConnection = db
	currentDBType = dbType

	return nil
}

func GetDBConnection() *sql.DB {
	return dbConnection
}

func CloseDBConnection() error {
	if dbConnection != nil {
		err := dbConnection.Close()
		dbConnection = nil
		return err
	}
	return nil
}
