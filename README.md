# gmail-1c-gateway

Срочный MVP FastAPI-прокси между будущим Gmail Add-on и локальным HTTP-сервисом 1С.

Gmail Add-on передаёт наружу только код производителя. Gateway берёт логин и пароль 1С из `.env`, обращается к 1С по Basic Auth и возвращает результат клиенту.

## Важно

Это только MVP для быстрого тестирования. В production endpoint `/api/v1/price-history` обязательно надо закрыть авторизацией внешнего API.

Пароль 1С не должен логироваться, передаваться внешним клиентом или возвращаться в ответах. Файл `.env` не коммитится в репозиторий.

## Настройка Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

После копирования `.env.example` в `.env` укажите реальные значения:

```env
ONEC_BASE_URL=http://127.0.0.1:8080/price-history
ONEC_LOGIN=your_1c_login
ONEC_PASSWORD=your_1c_password
REQUEST_TIMEOUT_SECONDS=10
```

## Endpoints

### GET /health

Проверка, что gateway запущен.

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

### POST /api/v1/price-history

Запрос истории цены по коду производителя.

```json
{
  "code": "0-905-21-102-2"
}
```

Gateway собирает URL:

```text
{ONEC_BASE_URL}/{code}
```

Затем делает GET-запрос в 1С с Basic Auth из `.env`.

## Тест PowerShell

```powershell
$body = @{
  code = "0-905-21-102-2"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/price-history" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

## Формат успешного ответа

Если 1С вернула `200`, gateway пробует распарсить тело как JSON. Если JSON распарсился, поле `data` содержит объект, а `raw` равно `null`. Если не распарсился, `data` равно `null`, а `raw` содержит текст.

```json
{
  "ok": true,
  "code": "0-905-21-102-2",
  "source_status": 200,
  "data": {},
  "raw": null
}
```

## Ошибки

Пустой `code` возвращает `400`.

Для ошибок 1С gateway возвращает:

```json
{
  "ok": false,
  "code": "0-905-21-102-2",
  "source_status": 404,
  "error": "Код не найден или путь к сервису 1С неверный",
  "raw": "..."
}
```

Обрабатываются:

- `401` от 1С: неверный логин или пароль 1С.
- `403` от 1С: нет прав.
- `404` от 1С: код не найден или путь неверный.
- `500` от 1С: ошибка сервера 1С.
- timeout при обращении к 1С.
- connection error при обращении к 1С.

## Перенос на другой ПК

1. Скопировать папку проекта без `.venv`.
2. На новом ПК создать `.env`.
3. Создать venv.
4. Установить `requirements.txt`.
5. Проверить `/health`.
6. Проверить доступ к 1С через `/api/v1/price-history`.
