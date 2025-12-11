package tools

import (
	"database/sql"
	"fmt"

	_ "github.com/go-sql-driver/mysql"
	_ "github.com/lib/pq"
)

var dbConnection *sql.DB
var currentDBType string

type DBType string

const (
	PostgresDB DBType = "postgres"
	MySQLDB    DBType = "mysql"
)

func (d DBType) GetConnectCreds() string {
	switch d {
	case PostgresDB:
		return "postgres"
	case MySQLDB:
		return "mysql"
	default:
		return ""
	}
}	


type ConnectDatabaseArgs struct {
	Type     DBType `json:"type"` // Тип базы данных ("postgres", "mysql")
	Host     string `json:"host"` // Хост базы данных
	Port     string `json:"port"` // Порт базы данных
	User     string `json:"user"`
	Password string `json:"password"` // Пароль для подключения к базе данных
	Name     string `json:"name"`     // Имя базы данных
}

func ConnectDatabaseDirect(cfg ConnectDatabaseArgs) (error, func() error) {
	var dsn string
	var driverName = cfg.Type.GetConnectCreds()
	currentDBType = string(cfg.Type)

	switch cfg.Type {
	case PostgresDB:
		dsn = fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable", cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.Name)
	case MySQLDB:
		dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true", cfg.User, cfg.Password, cfg.Host, cfg.Port, cfg.Name)
	default:
		return fmt.Errorf("неподдерживаемый тип базы данных: %s", cfg.Type), nil
	}

	db, err := sql.Open(driverName, dsn)
	if err != nil {
		return fmt.Errorf("ошибка открытия соединения: %w", err), nil
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return fmt.Errorf("ошибка подключения к базе данных: %w", err), nil
	}

	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)

	dbConnection = db

	return nil, func() error {
		return db.Close()
	}
}
