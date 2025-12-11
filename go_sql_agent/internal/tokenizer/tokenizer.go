package tokenizer

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"regexp"
	"strings"
	"sync"
)

// TokenType представляет тип токенизируемых данных
type TokenType string

const (
	TokenTypeName     TokenType = "NAME"     // ФИО, имена
	TokenTypeDate     TokenType = "DATE"     // Даты
	TokenTypeNumber   TokenType = "NUM"      // Числа (зарплаты, суммы и т.д.)
	TokenTypeID       TokenType = "ID"       // Идентификаторы
	TokenTypeAddress  TokenType = "ADDR"     // Адреса
	TokenTypePhone    TokenType = "PHONE"    // Телефоны
	TokenTypeEmail    TokenType = "EMAIL"    // Email адреса
	TokenTypeDiagnosis TokenType = "DIAG"    // Диагнозы
	TokenTypeDrug     TokenType = "DRUG"     // Названия препаратов
)

// Tokenizer управляет токенизацией и детокенизацией данных
type Tokenizer struct {
	enabled         bool
	mu              sync.RWMutex
	tokenMap        map[string]string // оригинал -> токен
	reverseMap      map[string]string // токен -> оригинал
	counters        map[TokenType]int // счетчики для каждого типа
	patterns        map[TokenType]*regexp.Regexp
	sensitiveFields []string // список чувствительных полей для автоматической маскировки
}

// Config конфигурация токенизатора
type Config struct {
	Enabled         bool
	SensitiveFields []string // поля, которые нужно маскировать
	UseHashing      bool     // использовать ли хеширование вместо счетчиков
}

// DefaultConfig возвращает конфигурацию по умолчанию
func DefaultConfig() Config {
	return Config{
		Enabled: true,
		SensitiveFields: []string{
			"name", "full_name", "first_name", "last_name", "middle_name",
			"phone", "email", "address", "birth_date", "birthdate",
			"salary", "income", "account", "card_number",
			"diagnosis", "disease", "drug", "medication", "prescription",
		},
		UseHashing: false,
	}
}

var globalTokenizer *Tokenizer

// Init инициализирует глобальный токенизатор
func Init(cfg Config) {
	globalTokenizer = New(cfg)
}

// GetTokenizer возвращает глобальный токенизатор
func GetTokenizer() *Tokenizer {
	if globalTokenizer == nil {
		globalTokenizer = New(DefaultConfig())
	}
	return globalTokenizer
}

// New создает новый токенизатор
func New(cfg Config) *Tokenizer {
	t := &Tokenizer{
		enabled:         cfg.Enabled,
		tokenMap:        make(map[string]string),
		reverseMap:      make(map[string]string),
		counters:        make(map[TokenType]int),
		patterns:        make(map[TokenType]*regexp.Regexp),
		sensitiveFields: cfg.SensitiveFields,
	}

	// Инициализируем паттерны для автоматического определения типов данных
	t.patterns[TokenTypeDate] = regexp.MustCompile(`\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}`)
	t.patterns[TokenTypeEmail] = regexp.MustCompile(`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`)
	t.patterns[TokenTypePhone] = regexp.MustCompile(`\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}`)

	return t
}

// IsEnabled проверяет, включена ли токенизация
func (t *Tokenizer) IsEnabled() bool {
	return t.enabled
}

// SetEnabled включает/выключает токенизацию
func (t *Tokenizer) SetEnabled(enabled bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.enabled = enabled
}

// Tokenize заменяет значение на токен
func (t *Tokenizer) Tokenize(value string, tokenType TokenType) string {
	if !t.enabled || value == "" {
		return value
	}

	t.mu.Lock()
	defer t.mu.Unlock()

	// Проверяем, есть ли уже токен для этого значения
	if token, exists := t.tokenMap[value]; exists {
		return token
	}

	// Создаем новый токен
	t.counters[tokenType]++
	token := fmt.Sprintf("%s_%03d", tokenType, t.counters[tokenType])

	// Сохраняем маппинги
	t.tokenMap[value] = token
	t.reverseMap[token] = value

	return token
}

// TokenizeWithHash создает токен на основе хеша значения
func (t *Tokenizer) TokenizeWithHash(value string, tokenType TokenType) string {
	if !t.enabled || value == "" {
		return value
	}

	t.mu.Lock()
	defer t.mu.Unlock()

	// Проверяем, есть ли уже токен для этого значения
	if token, exists := t.tokenMap[value]; exists {
		return token
	}

	// Создаем хеш
	hash := sha256.Sum256([]byte(value))
	hashStr := hex.EncodeToString(hash[:])[:8] // берем первые 8 символов

	token := fmt.Sprintf("%s_%s", tokenType, hashStr)

	// Сохраняем маппинги
	t.tokenMap[value] = token
	t.reverseMap[token] = value

	return token
}

// Detokenize восстанавливает оригинальное значение из токена
func (t *Tokenizer) Detokenize(token string) string {
	if !t.enabled || token == "" {
		return token
	}

	t.mu.RLock()
	defer t.mu.RUnlock()

	if value, exists := t.reverseMap[token]; exists {
		return value
	}

	return token
}

// TokenizeMap маскирует данные в map[string]interface{}
func (t *Tokenizer) TokenizeMap(data map[string]interface{}) map[string]interface{} {
	if !t.enabled {
		return data
	}

	result := make(map[string]interface{})
	for key, value := range data {
		result[key] = t.tokenizeValue(key, value)
	}
	return result
}

// DetokenizeMap восстанавливает данные в map[string]interface{}
func (t *Tokenizer) DetokenizeMap(data map[string]interface{}) map[string]interface{} {
	if !t.enabled {
		return data
	}

	result := make(map[string]interface{})
	for key, value := range data {
		result[key] = t.detokenizeValue(value)
	}
	return result
}

// tokenizeValue маскирует значение в зависимости от ключа
func (t *Tokenizer) tokenizeValue(key string, value interface{}) interface{} {
	strValue, ok := value.(string)
	if !ok {
		return value
	}

	// Определяем тип токена по имени поля
	tokenType := t.detectTokenType(key, strValue)
	if tokenType == "" {
		return value
	}

	return t.Tokenize(strValue, tokenType)
}

// detokenizeValue восстанавливает значение
func (t *Tokenizer) detokenizeValue(value interface{}) interface{} {
	strValue, ok := value.(string)
	if !ok {
		return value
	}

	return t.Detokenize(strValue)
}

// detectTokenType определяет тип токена на основе имени поля
func (t *Tokenizer) detectTokenType(fieldName, value string) TokenType {
	fieldLower := strings.ToLower(fieldName)

	// Проверяем, является ли поле чувствительным
	isSensitive := false
	for _, sf := range t.sensitiveFields {
		if strings.Contains(fieldLower, strings.ToLower(sf)) {
			isSensitive = true
			break
		}
	}

	if !isSensitive {
		return ""
	}

	// Определяем тип на основе имени поля
	switch {
	case strings.Contains(fieldLower, "name") || strings.Contains(fieldLower, "fio"):
		return TokenTypeName
	case strings.Contains(fieldLower, "date") || strings.Contains(fieldLower, "birth"):
		return TokenTypeDate
	case strings.Contains(fieldLower, "phone") || strings.Contains(fieldLower, "tel"):
		return TokenTypePhone
	case strings.Contains(fieldLower, "email") || strings.Contains(fieldLower, "mail"):
		return TokenTypeEmail
	case strings.Contains(fieldLower, "address") || strings.Contains(fieldLower, "addr"):
		return TokenTypeAddress
	case strings.Contains(fieldLower, "salary") || strings.Contains(fieldLower, "income") || strings.Contains(fieldLower, "amount"):
		return TokenTypeNumber
	case strings.Contains(fieldLower, "id"):
		return TokenTypeID
	case strings.Contains(fieldLower, "diagnosis") || strings.Contains(fieldLower, "disease"):
		return TokenTypeDiagnosis
	case strings.Contains(fieldLower, "drug") || strings.Contains(fieldLower, "medication") || strings.Contains(fieldLower, "prescription"):
		return TokenTypeDrug
	default:
		// Пробуем определить по паттернам
		for tokenType, pattern := range t.patterns {
			if pattern.MatchString(value) {
				return tokenType
			}
		}
	}

	return TokenTypeName // по умолчанию
}

// TokenizeSlice маскирует срез данных
func (t *Tokenizer) TokenizeSlice(data []map[string]interface{}) []map[string]interface{} {
	if !t.enabled {
		return data
	}

	result := make([]map[string]interface{}, len(data))
	for i, item := range data {
		result[i] = t.TokenizeMap(item)
	}
	return result
}

// DetokenizeSlice восстанавливает срез данных
func (t *Tokenizer) DetokenizeSlice(data []map[string]interface{}) []map[string]interface{} {
	if !t.enabled {
		return data
	}

	result := make([]map[string]interface{}, len(data))
	for i, item := range data {
		result[i] = t.DetokenizeMap(item)
	}
	return result
}

// TokenizeString маскирует все токены в строке
func (t *Tokenizer) TokenizeString(text string) string {
	if !t.enabled {
		return text
	}

	result := text

	// Применяем все известные токены
	t.mu.RLock()
	defer t.mu.RUnlock()

	for original, token := range t.tokenMap {
		result = strings.ReplaceAll(result, original, token)
	}

	return result
}

// DetokenizeString восстанавливает все токены в строке
func (t *Tokenizer) DetokenizeString(text string) string {
	if !t.enabled {
		return text
	}

	result := text

	// Применяем все известные токены в обратном порядке
	t.mu.RLock()
	defer t.mu.RUnlock()

	for token, original := range t.reverseMap {
		result = strings.ReplaceAll(result, token, original)
	}

	return result
}

// GetStats возвращает статистику токенизации
func (t *Tokenizer) GetStats() map[string]interface{} {
	t.mu.RLock()
	defer t.mu.RUnlock()

	return map[string]interface{}{
		"enabled":       t.enabled,
		"total_tokens":  len(t.tokenMap),
		"counters":      t.counters,
		"token_types":   len(t.counters),
	}
}

// Clear очищает все токены
func (t *Tokenizer) Clear() {
	t.mu.Lock()
	defer t.mu.Unlock()

	t.tokenMap = make(map[string]string)
	t.reverseMap = make(map[string]string)
	t.counters = make(map[TokenType]int)
}

// Глобальные функции для удобства
func Tokenize(value string, tokenType TokenType) string {
	return GetTokenizer().Tokenize(value, tokenType)
}

func Detokenize(token string) string {
	return GetTokenizer().Detokenize(token)
}

func TokenizeMap(data map[string]interface{}) map[string]interface{} {
	return GetTokenizer().TokenizeMap(data)
}

func DetokenizeMap(data map[string]interface{}) map[string]interface{} {
	return GetTokenizer().DetokenizeMap(data)
}

func TokenizeSlice(data []map[string]interface{}) []map[string]interface{} {
	return GetTokenizer().TokenizeSlice(data)
}

func DetokenizeSlice(data []map[string]interface{}) []map[string]interface{} {
	return GetTokenizer().DetokenizeSlice(data)
}