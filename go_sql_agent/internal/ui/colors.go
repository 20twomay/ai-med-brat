package ui

import (
	"fmt"

	"github.com/fatih/color"
)

var (
	// Основные цвета
	Green   = color.New(color.FgGreen)
	Red     = color.New(color.FgRed)
	Yellow  = color.New(color.FgYellow)
	Blue    = color.New(color.FgBlue)
	Cyan    = color.New(color.FgCyan)
	Magenta = color.New(color.FgMagenta)
	White   = color.New(color.FgWhite)

	// Жирный текст
	Bold      = color.New(color.Bold)
	BoldGreen = color.New(color.FgGreen, color.Bold)
	BoldRed   = color.New(color.FgRed, color.Bold)
	BoldBlue  = color.New(color.FgBlue, color.Bold)
	BoldCyan  = color.New(color.FgCyan, color.Bold)

	// Фоны
	BgGreen  = color.New(color.BgGreen, color.FgBlack)
	BgRed    = color.New(color.BgRed, color.FgWhite)
	BgYellow = color.New(color.BgYellow, color.FgBlack)
	BgBlue   = color.New(color.BgBlue, color.FgWhite)
)

// Success выводит сообщение об успехе
func Success(format string, args ...interface{}) {
	fmt.Print("✅ ")
	Green.Printf(format+"\n", args...)
}

// Error выводит сообщение об ошибке
func Error(format string, args ...interface{}) {
	fmt.Print("❌ ")
	Red.Printf(format+"\n", args...)
}

// Warning выводит предупреждение
func Warning(format string, args ...interface{}) {
	fmt.Print("⚠️  ")
	Yellow.Printf(format+"\n", args...)
}

// Info выводит информационное сообщение
func Info(format string, args ...interface{}) {
	fmt.Print("ℹ️  ")
	Cyan.Printf(format+"\n", args...)
}

// Header выводит заголовок секции
func Header(text string) {
	fmt.Println()
	BoldCyan.Println("=== " + text + " ===")
	fmt.Println()
}

// Subheader выводит подзаголовок
func Subheader(text string) {
	fmt.Println()
	BoldBlue.Println("--- " + text + " ---")
}

// Item выводит элемент списка
func Item(format string, args ...interface{}) {
	fmt.Print("  • ")
	fmt.Printf(format+"\n", args...)
}

// KeyValue выводит пару ключ-значение
func KeyValue(key, value string) {
	BoldWhite := color.New(color.Bold)
	fmt.Print("  ")
	BoldWhite.Print(key + ": ")
	fmt.Println(value)
}

// Section выводит именованную секцию
func Section(name string, fn func()) {
	Header(name)
	fn()
	fmt.Println()
}

// Box выводит текст в рамке
func Box(text string) {
	width := len(text) + 4
	border := "╔" + repeatString("═", width-2) + "╗"
	bottom := "╚" + repeatString("═", width-2) + "╝"

	BoldCyan.Println(border)
	BoldCyan.Print("║ ")
	BoldWhite := color.New(color.Bold)
	BoldWhite.Print(text)
	BoldCyan.Println(" ║")
	BoldCyan.Println(bottom)
}

// Table выводит таблицу
type Table struct {
	Headers []string
	Rows    [][]string
}

func (t *Table) Print() {
	if len(t.Headers) == 0 {
		return
	}

	// Вычисляем ширину колонок
	colWidths := make([]int, len(t.Headers))
	for i, h := range t.Headers {
		colWidths[i] = len(h)
	}
	for _, row := range t.Rows {
		for i, cell := range row {
			if i < len(colWidths) && len(cell) > colWidths[i] {
				colWidths[i] = len(cell)
			}
		}
	}

	// Печатаем заголовки
	fmt.Print("  ")
	for i, h := range t.Headers {
		BoldCyan.Print(padRight(h, colWidths[i]))
		if i < len(t.Headers)-1 {
			fmt.Print(" │ ")
		}
	}
	fmt.Println()

	// Печатаем разделитель
	fmt.Print("  ")
	for i, w := range colWidths {
		fmt.Print(repeatString("─", w))
		if i < len(colWidths)-1 {
			fmt.Print("─┼─")
		}
	}
	fmt.Println()

	// Печатаем строки
	for _, row := range t.Rows {
		fmt.Print("  ")
		for i, cell := range row {
			if i < len(colWidths) {
				fmt.Print(padRight(cell, colWidths[i]))
				if i < len(row)-1 {
					fmt.Print(" │ ")
				}
			}
		}
		fmt.Println()
	}
}

// Progress выводит индикатор прогресса
func Progress(current, total int, label string) {
	percentage := float64(current) / float64(total) * 100
	barWidth := 40
	filled := int(float64(barWidth) * float64(current) / float64(total))

	fmt.Print("\r  ")
	Cyan.Print(label + ": [")

	for i := 0; i < barWidth; i++ {
		if i < filled {
			Green.Print("█")
		} else {
			fmt.Print("░")
		}
	}

	Cyan.Printf("] %d/%d (%.1f%%)", current, total, percentage)

	if current == total {
		fmt.Println()
	}
}

// Spinner выводит спиннер загрузки
type Spinner struct {
	frames []string
	index  int
}

func NewSpinner() *Spinner {
	return &Spinner{
		frames: []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"},
		index:  0,
	}
}

func (s *Spinner) Next() string {
	frame := s.frames[s.index]
	s.index = (s.index + 1) % len(s.frames)
	return frame
}

// Badge выводит значок с текстом
func Badge(text string, colorAttr color.Attribute) {
	badge := color.New(colorAttr, color.Bold)
	badge.Printf(" %s ", text)
}

// SuccessBadge выводит зеленый значок
func SuccessBadge(text string) {
	Badge(text, color.BgGreen)
}

// ErrorBadge выводит красный значок
func ErrorBadge(text string) {
	Badge(text, color.BgRed)
}

// WarningBadge выводит желтый значок
func WarningBadge(text string) {
	Badge(text, color.BgYellow)
}

// InfoBadge выводит синий значок
func InfoBadge(text string) {
	Badge(text, color.BgBlue)
}

// Вспомогательные функции
func padRight(s string, width int) string {
	if len(s) >= width {
		return s
	}
	return s + repeatString(" ", width-len(s))
}

func repeatString(s string, count int) string {
	result := ""
	for i := 0; i < count; i++ {
		result += s
	}
	return result
}

// PrintLogo выводит логотип приложения
func PrintLogo() {
	logo := `
   _____ ____    __       ___                    __
  / ___// __ \  / /      /   | ____ ____  ____  / /_
  \__ \/ / / / / /      / /| |/ __  / _ \/ __ \/ __/
 ___/ / /_/ / / /___   / ___ / /_/ /  __/ / / / /_
/____/\___\_\/_____/  /_/  |_\__, /\___/_/ /_/\__/
                            /____/
`
	BoldCyan.Println(logo)
	Cyan.Println("    Медицинский SQL агент с токенизацией данных")
	fmt.Println()
}