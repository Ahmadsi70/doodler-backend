# نصب Story

```powershell
cd C:\Users\badri\Story
pip install -r requirements.txt
cd remotion
npm install
cd ..
```

پیش‌نیاز Williams: `cd C:\Users\badri\انیمیشن; npm run build`

اگر Pro با خطای `Cannot find module '@rspack/binding-win32-x64-msvc'` افتاد:

```powershell
cd C:\Users\badri\Story\remotion
npm install @rspack/binding-win32-x64-msvc
```
