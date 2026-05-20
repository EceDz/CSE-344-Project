# EventRadar Backend

Bu klasor EventRadar projesinin backend servisidir. Veriler SQLite database dosyasinda tutulur:

```text
eventradar.sqlite3
```

## Calistirma

```powershell
cd C:\Users\piina\Desktop\CSE344Proje\backend
python server.py
```

Servis adresi:

```text
http://127.0.0.1:8000
```

Varsayilan admin:

```text
admin@eventradar.com
admin123
```

## Database

Backend su tablolari olusturur:

- `users`: kayitli kullanicilar
- `sessions`: giris token kayitlari
- `events`: etkinlikler
- `follows`: kullanicilarin takip ettigi etkinlikler
- `event_sources`: bilet sitelerinden gelen etkinliklerin kaynak/id eslestirmesi
- `import_runs`: her ice aktarma isleminin ozeti

## Bilet sitesi importu

Admin token ile su endpoint kullanilir:

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"email":"admin@eventradar.com","password":"admin123"}'
$headers = @{ Authorization = "Bearer $($login.token)" }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/import-events?limit=30" -Headers $headers -ContentType "application/json" -Body "{}"
```

Onizleme icin:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/import-events?limit=10" -Headers $headers
```

Frontend admin panelinde de `Import Ticket Sites` butonu ayni islemi yapar.

## Ana API uclari

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`
- `PUT /api/me`
- `GET /api/events`
- `POST /api/events` admin
- `GET /api/events/{id}`
- `PUT /api/events/{id}` admin
- `DELETE /api/events/{id}` admin
- `POST /api/events/{id}/follow`
- `DELETE /api/events/{id}/follow`
- `GET /api/me/followed`
- `GET /api/users` admin
- `POST /api/users` admin
- `PUT /api/users/{email}` admin
- `DELETE /api/users/{email}` admin
- `GET /api/import-events` admin, onizleme
- `POST /api/import-events` admin, database'e kaydet

## Email notifications

User settings includes `Email notifications`. When enabled, followed-event emails are handled by:

```text
POST /api/me/notifications
```

If SMTP environment variables are set, the backend sends real email:

```powershell
$env:EVENTRADAR_SMTP_HOST="smtp.example.com"
$env:EVENTRADAR_SMTP_PORT="587"
$env:EVENTRADAR_SMTP_USER="user@example.com"
$env:EVENTRADAR_SMTP_PASSWORD="password"
$env:EVENTRADAR_SMTP_FROM="EventRadar <user@example.com>"
python server.py
```

If SMTP is not configured, the email is saved in `notification_logs` with status `logged`.

## Google Maps

The frontend uses Google Maps web links for venue search and directions. No API key is required for these links.
