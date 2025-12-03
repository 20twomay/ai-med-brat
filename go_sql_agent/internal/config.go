package internal

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	Qwen     QwenModelConfig
	Database DatabaseConfig
}

type DatabaseConfig struct {
	Type     string // postgres, mysql
	Host     string
	Port     string
	User     string
	Password string
	Name     string
}

func MustLoad(envPath string) Config {
	if envPath == "" || !strings.Contains(envPath, ".env") {
		panic("env path must be provided")
	}

	viper.SetConfigFile(envPath)
	viper.AutomaticEnv()

	if err := viper.ReadInConfig(); err != nil {
		panic(err)
	}

	cfg := Config{
		Qwen: QwenModelConfig{
			Model:   getEnvOrDefault("QWEN_MODEL", "qwen/qwen3-coder-30b-a3b-instruct"),
			APIKey:  viper.GetString("QWEN_API_KEY"),
			BaseURL: viper.GetString("QWEN_BASE_URL"),
		},
		Database: DatabaseConfig{
			Type:     getEnvOrDefault("DB_TYPE", "postgres"),
			Host:     getEnvOrDefault("DB_HOST", "localhost"),
			Port:     getEnvOrDefault("DB_PORT", "5432"),
			User:     viper.GetString("DB_USER"),
			Password: viper.GetString("DB_PASSWORD"),
			Name:     viper.GetString("DB_NAME"),
		},
	}

	if err := cfg.Validate(); err != nil {
		panic(err)
	}

	return cfg
}

func (c *Config) Validate() error {
	if c.Qwen.APIKey == "" {
		return fmt.Errorf("QWEN_API_KEY is required")
	}
	if c.Qwen.BaseURL == "" {
		return fmt.Errorf("QWEN_BASE_URL is required")
	}

	if c.Database.User == "" {
		return fmt.Errorf("DB_USER is required")
	}
	if c.Database.Password == "" {
		return fmt.Errorf("DB_PASSWORD is required")
	}
	if c.Database.Name == "" {
		return fmt.Errorf("DB_NAME is required")
	}
	if c.Database.Type != "postgres" && c.Database.Type != "mysql" {
		return fmt.Errorf("DB_TYPE must be 'postgres' or 'mysql', got: %s", c.Database.Type)
	}

	return nil
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := viper.GetString(key); value != "" {
		return value
	}
	return defaultValue
}
