# בלעם — סוכן ידע לפרשת שבוע

## תיאור
סוכן AI לכל פרשות התורה עם RAG על טקסט התורה ופרשנים קלאסיים מ-Sefaria. מציין ציטוט מדויק (פרק:פסוק + מפרש) בכל תשובה. המפתח Anthropic מוזן ע"י המשתמש ב-UI ונשמר רק ב-localStorage — השרת לא שומר אותו.

## סטאק
- **Backend**: Flask (Python) + BM25 RAG מקומי
- **Frontend**: PWA סטטי (מוגש מאותו שירות)
- **AI**: Anthropic Claude API (מפתח מצד הלקוח בלבד)
- **מקורות**: Sefaria API — תורה + פרשנים קלאסיים
- **דפלוי**: Render (port 5007 מקומית; ב-Render נקבע ע"י PORT)

## מבנה
```
data/           54 תיקיות פרשה: 5,846 פסוקים + 179,131 פירושים (JSON מ-Sefaria)
scripts/        fetch_sefaria.py — שליפה חד-פעמית
backend/        Flask app + BM25 + KB
frontend/       PWA סטטי
```

## הרצה מקומית
```bash
cd backend
pip install -r requirements.txt
python ingest.py --parasha-dir ../data/balak   # פעם אחת
python app.py   # http://localhost:5007
```

## הוספת פרשה נוספת
```bash
cd scripts
python fetch_sefaria.py --parasha <שם הפרשה באנגלית>
cd ../backend
python ingest.py --parasha-dir ../data/<slug>
```
`ingest.py` מוסיף ל-KB הקיים, לא מוחק פרשות קודמות.
