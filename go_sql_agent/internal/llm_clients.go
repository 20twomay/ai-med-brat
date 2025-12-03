package internal

import (
	"context"
	"encoding/json"
	"fmt"
	"iter"
	"strings"

	openai "github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
	"github.com/openai/openai-go/v3/shared"

	"google.golang.org/adk/model"
	"google.golang.org/genai"
)

// ===========================
// Empty Model
// ===========================

type EmptyModel struct{}

func NewEmptyModel() model.LLM {
	return EmptyModel{}
}

func (e EmptyModel) GenerateContent(ctx context.Context, req *model.LLMRequest, stream bool) iter.Seq2[*model.LLMResponse, error] {
	// Возвращаем функцию, которая при первом же вызове возвращает false,
	// сигнализируя об окончании последовательности.
	return func(yield func(*model.LLMResponse, error) bool) {
		// Ничего не делаем, просто выходим.
		// Цикл for...range по этому итератору не выполнит ни одной итерации.
	}
}

func (e EmptyModel) Name() string {
	return "EmptyModel"
}

// ===========================
// Qwen Model
// ===========================

type QwenModelConfig struct {
	Model   string
	APIKey  string
	BaseURL string
}

type QwenModel struct {
	client openai.Client

	config QwenModelConfig
}

func NewQwenOpenAIModel(cfg QwenModelConfig) *QwenModel {
	opts := []option.RequestOption{
		option.WithAPIKey(cfg.APIKey),
	}
	if cfg.BaseURL != "" {
		opts = append(opts, option.WithBaseURL(cfg.BaseURL))
	}

	client := openai.NewClient(opts...)

	return &QwenModel{
		client: client,
		config: cfg,
	}
}

func (m *QwenModel) Name() string {
	return m.config.Model
}

func (m *QwenModel) GenerateContent(ctx context.Context, req *model.LLMRequest, stream bool) iter.Seq2[*model.LLMResponse, error] {
	// Собираем сообщения
	messages := []openai.ChatCompletionMessageParamUnion{} // Добавляем системный промпт, если есть
	if req.Config != nil && req.Config.SystemInstruction != nil {
		var sysText string
		for _, part := range req.Config.SystemInstruction.Parts {
			if part.Text != "" {
				sysText += part.Text
			}
		}
		if sysText != "" {
			messages = append(messages, openai.SystemMessage(sysText))
		}
	}

	// Добавляем user сообщения и результаты функций
	for _, content := range req.Contents {
		// Собираем текст из всех частей
		var text string
		var hasFunctionCall bool
		var hasFunctionResponse bool

		for _, part := range content.Parts {
			if part.Text != "" {
				text += part.Text
			}
			if part.FunctionCall != nil {
				hasFunctionCall = true
				// Формируем JSON вызова функции для истории
				funcCallJSON := map[string]interface{}{
					"name":      part.FunctionCall.Name,
					"arguments": part.FunctionCall.Args,
				}
				callJSON, _ := json.Marshal(funcCallJSON)
				text += string(callJSON)
			}
			if part.FunctionResponse != nil {
				hasFunctionResponse = true
				// Формируем текст результата функции
				respJSON, _ := json.Marshal(part.FunctionResponse.Response)
				text += fmt.Sprintf("\nРезультат выполнения функции %s: %s\nТеперь вызови следующую функцию в JSON формате.", part.FunctionResponse.Name, string(respJSON))
			}
		}

		if text != "" {
			// Определяем роль сообщения
			if content.Role == genai.RoleUser || hasFunctionResponse {
				messages = append(messages, openai.UserMessage(text))
			} else if content.Role == genai.RoleModel || hasFunctionCall {
				messages = append(messages, openai.AssistantMessage(text))
			}
		}
	}

	params := openai.ChatCompletionNewParams{
		Model:    shared.ChatModel(m.config.Model),
		Messages: messages,
	}

	// Конфигурация (температура, top_p и др.)
	if cfg := req.Config; cfg != nil {
		if cfg.Temperature != nil {
			params.Temperature = openai.Float(float64(*cfg.Temperature))
		}
		if cfg.TopP != nil {
			params.TopP = openai.Float(float64(*cfg.TopP))
		}
		if cfg.MaxOutputTokens != 0 {
			params.MaxTokens = openai.Int(int64(cfg.MaxOutputTokens))
		}
	}

	if stream {
		// Стриминг
		streamResp := m.client.Chat.Completions.NewStreaming(ctx, params)

		return func(yield func(*model.LLMResponse, error) bool) {
			for streamResp.Next() {
				chunk := streamResp.Current()
				if len(chunk.Choices) == 0 {
					continue
				}

				choice := chunk.Choices[0]
				parts := []*genai.Part{}

				// Обработка текста
				if choice.Delta.Content != "" {
					parts = append(parts, &genai.Part{Text: choice.Delta.Content})
				}

				// Обработка tool calls
				if len(choice.Delta.ToolCalls) > 0 {
					for _, tc := range choice.Delta.ToolCalls {
						if tc.Function.Name != "" || tc.Function.Arguments != "" {
							parts = append(parts, &genai.Part{
								FunctionCall: &genai.FunctionCall{
									Name: tc.Function.Name,
									Args: map[string]interface{}{"arguments": tc.Function.Arguments},
								},
							})
						}
					}
				}

				if len(parts) > 0 {
					resp := &model.LLMResponse{
						Content: &genai.Content{
							Parts: parts,
							Role:  genai.RoleModel,
						},
						Partial: true,
					}

					if !yield(resp, nil) {
						return
					}
				}
			}

			if err := streamResp.Err(); err != nil {
				yield(nil, err)
				return
			}

			// Финальный ответ
			yield(&model.LLMResponse{
				Content: &genai.Content{
					Parts: []*genai.Part{{Text: ""}},
					Role:  genai.RoleModel,
				},
				TurnComplete: true,
			}, nil)
		}
	}

	// Нет стриминга: обычный запрос
	resp, err := m.client.Chat.Completions.New(ctx, params)
	if err != nil {
		return func(yield func(*model.LLMResponse, error) bool) {
			yield(nil, err)
		}
	}

	return func(yield func(*model.LLMResponse, error) bool) {
		if len(resp.Choices) == 0 {
			yield(nil, fmt.Errorf("no choices in response"))
			return
		}

		choice := resp.Choices[0]
		parts := []*genai.Part{}

		// Проверяем, есть ли tool calls в нативном формате
		if len(choice.Message.ToolCalls) > 0 {
			for _, tc := range choice.Message.ToolCalls {
				var args map[string]interface{}
				if err := json.Unmarshal([]byte(tc.Function.Arguments), &args); err != nil {
					args = map[string]interface{}{"raw": tc.Function.Arguments}
				}

				parts = append(parts, &genai.Part{
					FunctionCall: &genai.FunctionCall{
						Name: tc.Function.Name,
						Args: args,
					},
				})
			}
		} else if choice.Message.Content != "" {
			// Пробуем распарсить content как JSON вызов функции
			content := strings.TrimSpace(choice.Message.Content)

			// Если в ответе несколько JSON объектов, берём только первый
			lines := strings.Split(content, "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if line == "" {
					continue
				}

				var funcCall struct {
					Name      string                 `json:"name"`
					Arguments map[string]interface{} `json:"arguments"`
				}

				if err := json.Unmarshal([]byte(line), &funcCall); err == nil && funcCall.Name != "" {
					// Успешно распарсили первый JSON вызов функции
					parts = append(parts, &genai.Part{
						FunctionCall: &genai.FunctionCall{
							Name: funcCall.Name,
							Args: funcCall.Arguments,
						},
					})
					break // Берём только первый!
				}
			}

			// Если не удалось распарсить ни одной строки как function call
			if len(parts) == 0 {
				// Пробуем весь content целиком
				var funcCall struct {
					Name      string                 `json:"name"`
					Arguments map[string]interface{} `json:"arguments"`
				}
				if err := json.Unmarshal([]byte(content), &funcCall); err == nil && funcCall.Name != "" {
					parts = append(parts, &genai.Part{
						FunctionCall: &genai.FunctionCall{
							Name: funcCall.Name,
							Args: funcCall.Arguments,
						},
					})
				} else {
					// Это обычный текстовый ответ
					parts = append(parts, &genai.Part{Text: content})
				}
			}
		}

		if len(parts) == 0 {
			parts = append(parts, &genai.Part{Text: ""})
		}

		yield(&model.LLMResponse{
			Content: &genai.Content{
				Parts: parts,
				Role:  genai.RoleModel,
			},
			TurnComplete: true,
		}, nil)
	}
}
