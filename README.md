# 💸 Telegram Xarajatlar Boshqaruvi Boti (Aiogram 3.x)

Ushbu Telegram bot foydalanuvchilarning shaxsiy xarajatlarini samarali yuritishi, grafik vizual tahlillar olishi, Excel formatida hisobotlarni eksport va import qilishi hamda kun yakunida avtomatik eslatmalar olishi uchun mo'ljallangan.

Bot **Linux (Systemd)** va **Windows Server (Task Scheduler / Batch)** muhitlarida server o'chib-yonishida avtomatik va xatosiz ishga tushishi uchun barcha infratuzilmaviy skriptlar bilan ta'minlangan.

---

## 🚀 Asosiy Imkoniyatlar va Afzalliklar

1. **Telegram ID Bo'yicha Xavfsiz Izolatsiya (Data Isolation)**:
   - Har bir foydalanuvchi faqat o'zining xarajatlarini ko'ra oladi va boshqara oladi.
   - Boshqa foydalanuvchilar ma'lumotlarini ko'rish imkonsiz.
   - Administratorlar uchun alohida umumiy statistika paneli.

2. **Xarajatlar CRUD (Qo'shish, Ko'rish, Filtrlash, O'chirish)**:
   - Inline va Reply tugmalar yordamida tezkor xarajat kiritish.
   - Oziq-ovqat, Transport, Kommunal va b. tayyor va shaxsiy yangi kategoriyalar yaratish.
   - Sana tanlash (Bugun, Kecha yoki shaxsiy YYYY-MM-DD).

3. **📊 Grafik Vizual Tahlil (Matplotlib & Pandas)**:
   - Bugun, Shu Hafta, Shu Oy va Barcha davrlar bo'yicha **Pie Chart** (Donut) va **Bar Chart** grafik rasmli hisobotlarini olish.

4. **📁 Excel bilan Integratsiya**:
   - **Export**: Barcha xarajatlarni chiroyli formatlangan `.xlsx` faylda yuklab olish.
   - **Import**: Tayyor Excel namunasidan foydalanib ommaviy xarajatlarni botga yuklash (format va ma'lumot turlari validatsiyasi bilan).

5. **🔔 Kunlik Avtomatik Eslatma (APScheduler)**:
   - Har kuni soat 21:00 da (yoki foydalanuvchi belgilagan boshqa vaqtda) *"Bugun xarajatlaringizni kiritdingizmi?"* so'rovi va eslatmasi.

6. **⚡ Nolinchi Xatolik va Chidamlilik (Resilience)**:
   - **SQLite WAL mode**: Parallel async so'rovlarda `database is locked` xatoligi mutlaqo bo'lmaydi.
   - **Global Error Handler**: Bot kutilmagan xatolik tufayli to'xtab qolmaydi, log yozadi va adminga bildirishnoma yuboradi.

---

## 🛠 O'rnatish va Sozlash

### 1. `.env` faylini yaratish va sozlash
`TIMEMANAGEMENT` papkasida `.env` faylini yarating yoki `.env.example` nusxasini oling:

```bash
cp .env.example .env
```

`.env` ichiga BotFather'dan olingan `BOT_TOKEN` va Admin ID ingizni kiriting:
```env
BOT_TOKEN=7891234567:AAEb...
ADMIN_IDS=12345678,87654321
DB_URL=sqlite+aiosqlite:///expenses.db
DEFAULT_REMINDER_TIME=21:00
```

---

## 🐧 Linux Serverda Autostart (Ubuntu / Debian / CentOS)

Autostart o'rnatish skriptini ishga tushiring:

```bash
chmod +x deploy/install_linux.sh
sudo ./deploy/install_linux.sh
```

**Statusni tekshirish va loglar:**
```bash
sudo systemctl status timemanagement_bot
tail -f bot.log
```

---

## 🪟 Windows Serverda Autostart (Windows 10/11 / Windows Server)

1. `deploy/start_windows.bat` faylini ikki marta bosing (Python virtual environment va kutubxonalarni avtomatik o'rnatadi).
2. Windows Server o'chib-yonganda avtomatik fonda ishga tushishi uchun PowerShell ni **Administrator** sifatida ochib va quyidagi buyruqni bosing:

```powershell
Set-ExecutionPolicy Unrestricted -Scope Process
.\deploy\install_windows_task.ps1
```

Ushbu skript Windows Task Scheduler ichida server yoqilishi bilan botni ishga tushiradigan topshiriq shakllantiradi.

---

## 🧪 Sintaksis va Mantiqiy Tekshirish

Kodni sinash uchun:
```bash
python -m py_compile bot.py
```
