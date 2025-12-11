package logger

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"strings"
	"time"
)

// ANSI цветовые коды
const (
	colorReset   = "\033[0m"
	colorRed     = "\033[31m"
	colorGreen   = "\033[32m"
	colorYellow  = "\033[33m"
	colorOrange  = "\033[38;5;208m"
	colorMagenta = "\033[35m"
	colorGray    = "\033[90m"
	colorBold    = "\033[1m"
)

// contextKey тип для ключей в контексте
type contextKey string

const (
	// stageContextKey ключ для хранения названия стадии в контексте
	stageContextKey contextKey = "stage"
)

// LogLevel представляет уровень логирования
type LogLevel int

const (
	DEBUG LogLevel = iota
	INFO
	WARN
	ERROR
	FATAL
)

// String возвращает строковое представление уровня
func (l LogLevel) String() string {
	switch l {
	case DEBUG:
		return "DEBUG"
	case INFO:
		return "INFO"
	case WARN:
		return "WARN"
	case ERROR:
		return "ERROR"
	case FATAL:
		return "FATAL"
	default:
		return "UNKNOWN"
	}
}

// Color возвращает цвет для уровня логирования
func (l LogLevel) Color() string {
	switch l {
	case DEBUG:
		return colorGray
	case INFO:
		return colorYellow
	case WARN:
		return colorOrange
	case ERROR:
		return colorRed
	case FATAL:
		return colorRed + colorBold
	default:
		return colorReset
	}
}

// ParseLogLevel преобразует строку в LogLevel
func ParseLogLevel(level string) LogLevel {
	switch strings.ToUpper(level) {
	case "DEBUG":
		return DEBUG
	case "INFO":
		return INFO
	case "WARN", "WARNING":
		return WARN
	case "ERROR":
		return ERROR
	case "FATAL":
		return FATAL
	default:
		return INFO
	}
}

// Logger представляет структурированный логгер
type Logger struct {
	level      LogLevel
	logger     *log.Logger
	useEmoji   bool
	showTime   bool
	showCaller bool
}

// Config содержит конфигурацию логгера
type Config struct {
	Level      LogLevel
	Output     io.Writer
	ShowTime   bool
	ShowCaller bool
}

// DefaultConfig возвращает конфигурацию по умолчанию
func DefaultConfig() Config {
	return Config{
		Level:      INFO,
		Output:     os.Stdout,
		ShowTime:   true,
		ShowCaller: false,
	}
}

var defaultLogger *Logger

// New создает новый логгер с заданной конфигурацией
func New(cfg Config) *Logger {
	if cfg.Output == nil {
		cfg.Output = os.Stdout
	}

	return &Logger{
		level:      cfg.Level,
		logger:     log.New(cfg.Output, "", 0),
		showTime:   cfg.ShowTime,
		showCaller: cfg.ShowCaller,
	}
}

// Init инициализирует глобальный логгер
func Init(cfg Config) {
	defaultLogger = New(cfg)
}

// GetLogger возвращает глобальный логгер
func GetLogger() *Logger {
	if defaultLogger == nil {
		defaultLogger = New(DefaultConfig())
	}
	return defaultLogger
}

// WithStage добавляет название стадии в контекст
func WithStage(ctx context.Context, stage string) context.Context {
	return context.WithValue(ctx, stageContextKey, stage)
}

// GetStageFromContext извлекает название стадии из контекста
func GetStageFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	stage, ok := ctx.Value(stageContextKey).(string)
	if !ok {
		return ""
	}
	return stage
}

// log выводит сообщение с заданным уровнем, добавляя информацию о стадии из контекста
func (l *Logger) log(ctx context.Context, level LogLevel, format string, args ...interface{}) {
	if level < l.level {
		return
	}

	var b strings.Builder
	if l.showTime {
		t := time.Now().Format("2006-01-02 15:04:05")
		b.WriteString(colorGray)
		b.WriteString("[")
		b.WriteString(t)
		b.WriteString("]")
		b.WriteString(colorReset)
		b.WriteString(" ")
	}

	// Уровень логирования с цветом
	b.WriteString(level.Color())
	b.WriteString("[")
	b.WriteString(level.String())
	b.WriteString("]")
	b.WriteString(colorReset)
	b.WriteString(" ")

	// Добавляем стадию из контекста, если она есть (подсвечиваем)
	if stage := GetStageFromContext(ctx); stage != "" {
		b.WriteString(colorMagenta)
		b.WriteString("[")
		b.WriteString(stage)
		b.WriteString("]")
		b.WriteString(colorReset)
		b.WriteString(" ")
	}

	message := fmt.Sprintf(format, args...)

	l.logger.Printf("%s%s", b.String(), message)

	if level == FATAL {
		os.Exit(1)
	}
}

// Debug выводит debug сообщение с информацией из контекста
func (l *Logger) Debug(ctx context.Context, format string, args ...interface{}) {
	l.log(ctx, DEBUG, format, args...)
}

// Info выводит информационное сообщение с информацией из контекста
func (l *Logger) Info(ctx context.Context, format string, args ...interface{}) {
	l.log(ctx, INFO, format, args...)
}

// Warn выводит предупреждение с информацией из контекста
func (l *Logger) Warn(ctx context.Context, format string, args ...interface{}) {
	l.log(ctx, WARN, format, args...)
}

// Error выводит сообщение об ошибке с информацией из контекста
func (l *Logger) Error(ctx context.Context, format string, args ...interface{}) {
	l.log(ctx, ERROR, format, args...)
}

// Fatal выводит критическую ошибку с информацией из контекста и завершает программу
func (l *Logger) Fatal(ctx context.Context, format string, args ...interface{}) {
	l.log(ctx, FATAL, format, args...)
}

// Success выводит сообщение об успехе с информацией из контекста
func (l *Logger) Success(ctx context.Context, format string, args ...interface{}) {
	message := fmt.Sprintf(format, args...)
	colored := colorGreen + message + colorReset
	l.Info(ctx, "%s", colored)
}

// Progress выводит информацию о прогрессе с информацией из контекста
func (l *Logger) Progress(ctx context.Context, format string, args ...interface{}) {
	message := fmt.Sprintf(format, args...)
	l.Info(ctx, "[PROGRESS] %s", message)
}

// Глобальные функции для удобства
func Debug(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Debug(ctx, format, args...)
}

func Info(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Info(ctx, format, args...)
}

func Warn(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Warn(ctx, format, args...)
}

func Error(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Error(ctx, format, args...)
}

func Fatal(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Fatal(ctx, format, args...)
}

func Success(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Success(ctx, format, args...)
}

func Progress(ctx context.Context, format string, args ...interface{}) {
	GetLogger().Progress(ctx, format, args...)
}
