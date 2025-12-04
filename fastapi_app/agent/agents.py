"""
Агенты для обработки запросов
"""

import logging
import re
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from .models import ClarificationOutput, ClarifyResponse, ExecuteResponse
from .prompts import CLARIFICATION_PROMPT, DB_PROMPT, EXECUTION_PROMPT, SUMMARIZER_PROMPT
from .tools import execute_sql_tool, plot_chart_tool

logger = logging.getLogger(__name__)


class MedicalAnalyticsAgent:
    """Агент для анализа медицинских данных"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.tools = [execute_sql_tool, plot_chart_tool]
        self.llm_with_tools = llm.bind_tools(self.tools)
    
    def clarify_query(self, query: str) -> ClarifyResponse:
        """
        Проверяет запрос и определяет, нужны ли уточнения
        """
        logger.info(f"Clarify request: {query[:100]}...")
        
        # Формируем промпт
        sys_msg = SystemMessage(
            content=CLARIFICATION_PROMPT.format(
                db_prompt=DB_PROMPT,
                current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            )
        )
        
        user_msg = HumanMessage(content=query)
        
        # Вызываем LLM с структурированным выводом
        llm_with_structure = self.llm.with_structured_output(ClarificationOutput)
        response = llm_with_structure.invoke([sys_msg, user_msg])
        
        logger.info(
            f"Clarify response: is_valid={response.is_request_valid}, "
            f"needs_clarification={response.needs_clarification}"
        )
        
        # Формируем ответ
        if not response.is_request_valid:
            # Невалидный запрос
            return ClarifyResponse(
                is_request_valid=False,
                needs_clarification=False,
                message=response.message,
                suggestions=None
            )
        elif response.needs_clarification:
            # Нужны уточнения
            return ClarifyResponse(
                is_request_valid=True,
                needs_clarification=True,
                message=response.message,
                suggestions=response.suggestions or []
            )
        else:
            # Запрос готов к выполнению
            return ClarifyResponse(
                is_request_valid=True,
                needs_clarification=False,
                message=response.message,
                suggestions=None
            )
    
    def execute_query(self, query: str, max_iterations: int = 10) -> ExecuteResponse:
        """
        Выполняет анализ данных по запросу
        """
        logger.info(f"Execute request: {query[:100]}...")
        
        # Формируем промпт
        sys_msg = SystemMessage(
            content=EXECUTION_PROMPT.format(
                db_prompt=DB_PROMPT,
                current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            )
        )
        
        user_msg = HumanMessage(content=query)
        
        # Выполняем итерации worker
        messages = [user_msg]
        
        for iteration in range(max_iterations):
            logger.info(f"Execute iteration {iteration}/{max_iterations}")
            
            # Вызываем LLM с инструментами
            response = self.llm_with_tools.invoke([sys_msg] + messages)
            messages.append(response)
            
            # Если нет tool calls - заканчиваем
            if not response.tool_calls:
                logger.info("No tool calls, ending execution")
                break
            
            # Выполняем tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                logger.info(f"Executing tool: {tool_name}")
                
                try:
                    if tool_name == "execute_sql_tool":
                        result = execute_sql_tool.invoke(tool_args)
                    elif tool_name == "plot_chart_tool":
                        result = plot_chart_tool.invoke(tool_args)
                    else:
                        result = f"Unknown tool: {tool_name}"
                    
                    # Создаём ToolMessage
                    tool_message = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)
                    
                except Exception as tool_error:
                    logger.error(f"Tool error {tool_name}: {tool_error}", exc_info=True)
                    error_message = ToolMessage(
                        content=f"Error executing {tool_name}: {str(tool_error)}",
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(error_message)
        
        # Финальная суммаризация
        logger.info("Generating summary")
        summary_sys_msg = SystemMessage(
            content=SUMMARIZER_PROMPT.format(
                current_datetime=datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            )
        )
        
        summary = self.llm.invoke([summary_sys_msg] + messages)
        summary_text = summary.content if summary.content else ""
        summary_text = summary_text.strip()
        
        # Если summary пустой, берем последнее AI сообщение
        if not summary_text:
            logger.warning("Empty summary, using last AI message")
            ai_messages = [msg for msg in messages if isinstance(msg, AIMessage) and msg.content]
            if ai_messages:
                summary_text = ai_messages[-1].content
            else:
                summary_text = "Извините, не удалось сформировать ответ на ваш запрос."
        
        # Извлекаем графики
        charts = self._extract_charts_from_messages(messages)
        
        logger.info(f"Execute completed: {len(summary_text)} chars, {len(charts)} charts")
        
        return ExecuteResponse(
            result=summary_text,
            charts=charts
        )
    
    @staticmethod
    def _extract_charts_from_messages(messages: list) -> list[str]:
        """Извлекает пути к графикам из сообщений (поддерживает S3 URLs)"""
        charts = []
        for msg in messages:
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                # Ищем паттерн: CHART_GENERATED:filename.png|http://s3-url
                matches = re.findall(r"CHART_GENERATED:([^\s|]+\.png)(?:\|([^\s]+))?", msg.content)
                for match in matches:
                    filename = match[0]
                    s3_url = match[1] if len(match) > 1 and match[1] else None
                    
                    # Приоритет: S3 URL > локальный путь
                    if s3_url:
                        charts.append(s3_url)
                    else:
                        charts.append(f"/charts/{filename}")
        return charts
