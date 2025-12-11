package tools

import (
	"database/sql"
	"encoding/csv"
	"fmt"
	"os"
	"time"

	"github.com/20twomay/ai-med-brat/go_sql_agent/internal/tokenizer"
)

// ExportToCSV экспортирует результаты SQL запроса в CSV файл
// Данные детокенизируются перед записью в файл, чтобы в CSV были реальные значения
func ExportToCSV(rows *sql.Rows, filename string) (int, error) {
	tok := tokenizer.GetTokenizer()

	// Создаем файл
	file, err := os.Create(filename)
	if err != nil {
		return 0, fmt.Errorf("ошибка создания файла: %w", err)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// Получаем названия колонок
	columns, err := rows.Columns()
	if err != nil {
		return 0, fmt.Errorf("ошибка получения колонок: %w", err)
	}

	// Маппинг колонок на русские названия (для соответствия примерам)
	translatedColumns := translateColumns(columns)

	// Записываем заголовки
	if err := writer.Write(translatedColumns); err != nil {
		return 0, fmt.Errorf("ошибка записи заголовков: %w", err)
	}

	// Подготавливаем буферы для чтения данных
	values := make([]interface{}, len(columns))
	valuePtrs := make([]interface{}, len(columns))
	for i := range values {
		valuePtrs[i] = &values[i]
	}

	rowCount := 0
	for rows.Next() {
		if err := rows.Scan(valuePtrs...); err != nil {
			return rowCount, fmt.Errorf("ошибка чтения строки: %w", err)
		}

		// Конвертируем значения в строки и детокенизируем
		stringValues := make([]string, len(values))
		for i, val := range values {
			strVal := valueToString(val)

			// Детокенизируем значение перед записью в CSV
			// В CSV должны быть реальные данные, а не токены
			if tok.IsEnabled() && strVal != "" {
				strVal = tok.Detokenize(strVal)
			}

			stringValues[i] = strVal
		}

		if err := writer.Write(stringValues); err != nil {
			return rowCount, fmt.Errorf("ошибка записи строки: %w", err)
		}
		rowCount++
	}

	if err := rows.Err(); err != nil {
		return rowCount, fmt.Errorf("ошибка итерации по строкам: %w", err)
	}

	return rowCount, nil
}

// translateColumns переводит названия колонок на русский язык
func translateColumns(columns []string) []string {
	translations := map[string]string{
		// Диагнозы
		"code":          "код_мкб",
		"icd_code":      "код_мкб",
		"diagnosis":     "название_диагноза",
		"name":          "название_диагноза",
		"class":         "класс_заболевания",
		"disease_class": "класс_заболевания",

		// Пациенты
		"id":            "id",
		"patient_id":    "id",
		"birth_date":    "дата_рождения",
		"birthdate":     "дата_рождения",
		"date_of_birth": "дата_рождения",
		"gender":        "пол",
		"sex":           "пол",
		"district":      "район_проживания",
		"region":        "регион",
		"city":          "регион",

		// Рецепты
		"prescription_date": "дата_рецепта",
		"date":              "дата_рецепта",
		"created_at":        "дата_рецепта",
		"diagnosis_code":    "код_диагноза",
		"drug_code":         "код_препарата",
		"medicine_code":     "код_препарата",
		"medication_code":   "код_препарата",
	}

	result := make([]string, len(columns))
	for i, col := range columns {
		if translated, ok := translations[col]; ok {
			result[i] = translated
		} else {
			result[i] = col
		}
	}
	return result
}

// valueToString конвертирует значение любого типа в строку
func valueToString(val interface{}) string {
	if val == nil {
		return ""
	}

	switch v := val.(type) {
	case []byte:
		return string(v)
	case time.Time:
		// Определяем формат вывода в зависимости от наличия времени
		if v.Hour() == 0 && v.Minute() == 0 && v.Second() == 0 {
			return v.Format("2006-01-02")
		}
		return v.Format("2006-01-02 15:04:05")
	case int, int8, int16, int32, int64:
		return fmt.Sprintf("%d", v)
	case uint, uint8, uint16, uint32, uint64:
		return fmt.Sprintf("%d", v)
	case float32, float64:
		return fmt.Sprintf("%v", v)
	case bool:
		if v {
			return "true"
		}
		return "false"
	case string:
		return v
	default:
		return fmt.Sprintf("%v", v)
	}
}
