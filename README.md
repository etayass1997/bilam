# בלעם — סוכן ידע לפרשת שבוע

סוכן AI לפרשת שבוע (החל מפרשת בלק), עם RAG על טקסט התורה + פרשנים קלאסיים מ-[Sefaria](https://www.sefaria.org), וציטוט מדויק (פרק:פסוק + מפרש) בכל תשובה.

ארכיטקטורה: Flask על Render מגיש גם את ה-frontend הסטטי וגם את ה-backend (API) מאותו שירות + BM25 RAG מקומי + Anthropic API.

מפתח ה-Anthropic API מוזן ע"י המשתמש ב-UI, נשמר רק ב-`localStorage` של הדפדפן, ונשלח לשרת רק בזמן שאלה. השרת אינו מאחסן, רושם ללוג, או שומר את המפתח בשום שלב.

## מבנה הפרויקט

```
data/balak/        קבצי JSON (פסוק+פרשנות) שנוצרו ע"י scripts/fetch_sefaria.py
scripts/           שלב 1 — שליפה חד-פעמית מ-Sefaria API
backend/           Flask app + מנוע BM25 + KB
frontend/          PWA סטטי, מוגש ע"י backend/app.py
```

## הוספת פרשה נוספת

```
cd scripts
python fetch_sefaria.py --parasha <שם הפרשה באנגלית, למשל Pinchas>
cd ../backend
python ingest.py --parasha-dir ../data/<slug>
```

`ingest.py` מוסיף ל-KB הקיים (לא מוחק פרשות קודמות). שום קוד לא מניח שקיימת רק פרשת בלק.

## הרצה מקומית

```
cd backend
pip install -r requirements.txt
python ingest.py --parasha-dir ../data/balak   # פעם אחת, אם kb/kb_data.json לא קיים
python app.py                                    # רץ על http://localhost:5005
```

פתחו את `http://localhost:5005` בדפדפן (`BACKEND_URL` ב-`frontend/app.js` ריק בכוונה — ה-frontend מוגש מאותו שרת), הזינו מפתח Anthropic API משלכם, ושאלו שאלה.

## Deployment

### Render (frontend + backend, שירות אחד)

1. Push את הריפו ל-GitHub.
2. Render → New Web Service → מחברים את הריפו, **Root Directory: `backend`**.
3. Build command: `pip install -r requirements.txt`. Start command: כבר מוגדר ב-`Procfile` (`gunicorn app:app`).
4. **אין** להגדיר `ANTHROPIC_API_KEY` ב-Environment Variables — הסוכן הזה לא משתמש במפתח בצד השרת בכלל.
5. ודאו ש-`backend/kb/kb_data.json` נכלל ב-git (לא ב-`.gitignore`) כדי שהמאגר יהיה זמין ב-production.
6. כתובת השירות (`https://<your-service>.onrender.com`) מגישה גם את הדף הראשי וגם את ה-API — אין צורך ב-GitHub Pages.
