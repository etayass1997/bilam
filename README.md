# בלעם — תוסף ללימוד פרשת השבוע ב־ChatGPT

## שימוש בפלאפון

הממשק הנייד מאפשר חיפוש בפסוקי התורה ובמפרשים, ספירת מילה ונתוני פרשה בדפדפן. אפשר להוסיף אותו למסך הבית ב־Android וב־iPhone לאחר פריסה בכתובת HTTPS. חבילת הפריסה הכוללת את המאגר המלא נמצאת ב־[dist/bilam-mobile-web.zip](dist/bilam-mobile-web.zip). הוראות הפעלה והתקנה: [MOBILE.md](MOBILE.md). החיפוש דורש חיבור לשרת ואינו פועל ללא אינטרנט.

## גרסה עצמאית לשיתוף

החבילה [dist/bilam-standalone.zip](dist/bilam-standalone.zip) מכילה את **כל 184,977 המקורות** ואת סקריפט החיפוש, הספירה והייצוא למסמך Word. היא אינה דורשת Render, שרת MCP או מפתח API. המאגר חולק ל־12 קובצי פרשנות דחוסים ולקובץ פסוקים נפרד; גודל ה־ZIP הוא כ־53MB. לבנייה מחדש לאחר עדכון המאגר: `python scripts/build_standalone_plugin.py`.

התוסף דורש סביבת ChatGPT או Codex שמסוגלת להתקין Plugins, לקרוא את קובצי ה־Skill ולהריץ סקריפט Python מצורף. בדיקות מקומיות אימתו התאמה למנוע המקורי; **הפעלה של הסקריפט מתוך ChatGPT של משתמש אחר טרם אומתה**. הפצה דרך ספריית התוספים כפופה להרשאות חשבון, אימות מפתח וסקירת OpenAI. ראו [הוראות חבילת התוסף](plugins/bilam-standalone/README.md).

## גרסת שרת MCP

בלעם משלב מאגר מקומי של פסוקי התורה ופירושי פרשנים קלאסיים מ־Sefaria עם שיחה בתוך ChatGPT. חיפוש המקורות והספירות המדויקות מתבצעים בשרת MCP. הניסוח, ההשוואה בין פירושים והמשך השיחה מתבצעים ב־ChatGPT. אין צורך במפתח Claude או במפתח OpenAI API.

## מבנה

- `backend/server.py` — שרת MCP ב־Streamable HTTP בנתיב `/mcp/`, עם ארבעה כלים לקריאת המקורות.
- `backend/app.py` — נקודות HTTP לקריאת מקורות, בדיקת תקינות, ייצוא Word ודף כניסה. נתיב `/chat` הישן מחזיר `410`.
- `backend/rag_engine.py` ו־`backend/text_stats.py` — חיפוש BM25 וספירות דטרמיניסטיות על פסוקי התורה.
- `backend/kb/kb_data.json.gz` — מאגר 54 הפרשות. `data/` ו־`scripts/fetch_sefaria.py` משמשים לעדכון המאגר.
- `plugins/bilam/` — חבילת התוסף: `plugin.json`, מיומנות הלימוד, אייקון ותבנית חיבור MCP.
- `.agents/plugins/marketplace.json` — קטלוג מקומי להצגת התוסף בסביבת פיתוח תומכת.

## הרצה מקומית

נדרשת Python 3.12 ומעלה.

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 5007
```

בדקו את `http://127.0.0.1:5007/health` ואת כלי ה־MCP ב־`http://127.0.0.1:5007/mcp/` באמצעות MCP Inspector. הדף ב־`http://127.0.0.1:5007/` מציג את מצב המאגר. בקשת MCP רגילה אינה בקשת GET בדפדפן; יש להשתמש בלקוח MCP לבדיקה.

## פריסה וחיבור ל־ChatGPT

1. פרסו את הריפו ב־Render כ־Web Service עם **Root Directory: `backend`**. פקודת הבנייה: `pip install -r requirements.txt`. פקודת ההרצה ב־`backend/Procfile`. הקובץ `backend/kb/kb_data.json.gz` חייב להיכלל בפריסה.
2. הגדירו ב־Render את `PUBLIC_BASE_URL` לכתובת השירות הציבורית, למשל `https://bilam.onrender.com`. כך שרת MCP מאשר את שם המארח הנכון. אפשר להגדיר `PLUGIN_URL` לאחר יצירת קישור לתוסף, כדי שדף הבית יציג אליו קישור ישיר.
3. לאחר שהשירות עולה, בדקו `/health` ואת `https://<service>/mcp/` ב־MCP Inspector. השתמשו בכתובת עם לוכסן סופי.
4. הריצו משורש הפרויקט `python scripts/configure_plugin.py https://<service>`. הסקריפט ייצור `plugins/bilam/mcp.json` ו־`plugins/bilam/skills/torah-study/agents/openai.yaml` עם הכתובת האמיתית. עד אז התוסף המקומי מכיל הוראות בלבד.
5. הפעילו Developer mode ב־ChatGPT והוסיפו חיבור MCP חדש ב־ChatGPT Plugins עם כתובת `/mcp/`. לאחר זיהוי ארבעת הכלים, התקינו את התוסף המקומי מקטלוג הפרויקט או ארזו והגישו אותו לפי הרשאות החשבון. פרסום ציבורי דורש כתובת HTTPS יציבה, עמידה בדרישות הפרסום וסקירת OpenAI.
6. בדקו ב־ChatGPT שאלה על מקור, השוואת פירושים ושאלת ספירה. ודאו שהמקורות המצוטטים הוחזרו מהכלי ושהספירה נלקחה מתוצאת הכלי.

התוסף ניגש למאגר ציבורי לקריאה בלבד ולכן שרת MCP אינו דורש הזדהות. הוא אינו שולח בקשות למודל שפה. חיבור ChatGPT תלוי בזמינות Plugins ובהרשאות בחשבון או בסביבת העבודה.

## תחזוקת המאגר

```powershell
cd scripts
python fetch_sefaria.py --parasha Pinchas
cd ../backend
python ingest.py --parasha-dir ../data/pinchas
```

לבנייה מחדש מכל הקבצים הקיימים: `python ingest.py --all-data ../data` מתוך `backend`.

## תיעוד רשמי

- [בניית שרת MCP לתוסף](https://developers.openai.com/plugins/build/mcp-server)
- [אריזת Plugin](https://developers.openai.com/plugins/build/plugins)
- [חיבור ובדיקת Plugin ב־ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt)
