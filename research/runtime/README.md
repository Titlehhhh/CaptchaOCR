# research/runtime — рантайм без Python

**Что это.** Исходники и конфигурация «одной папки» для запуска нашего распознавателя **без
Python и без torch**: экспортированная модель ONNX + `onnxruntime` + препроцессинг + CTC-декод.

| файл | что |
|---|---|
| `csharp/Program.cs` | рантайм на C# (onnxruntime C API + WIC для чтения PNG) — самодостаточный exe, без питона |
| `native/config.json` | конфигурация рантайма: charset, высота глифа, параметры нормализации, путь к модели |

**Сборки намеренно не в git.** `onnxruntime.dll` (16.5 МБ), `captcha_runtime.exe` и `crnn_fp32.onnx`
(18.5 МБ) — это артефакты сборки и веса; они пересобираются и качаются. Всё, что нужно для
воспроизведения, — в коде и в отчёте.

**Как собрать** (команды и замеры — в `reports/research2/T2_onnx_runtime.md`):

```powershell
# 1) экспорт и квантизация (пишет bench/models/*.onnx, они в .gitignore)
.venv-gpu\Scripts\python.exe bench\export_onnx.py

# 2) C#-рантайм: собрать exe (нужен .NET SDK; WIC — только Windows)
dotnet publish research\runtime\csharp -c Release -o research\runtime\native

# 3) положить рядом с exe: onnxruntime.dll (релиз 1.30.0) и модель
#    research\runtime\native\config.json указывает путь к .onnx
```

**Проверено:** torch == Python(ORT) == C == C# дают одинаковый результат на 20 полосах; препроцессинг
C/C# отличается от PIL на ≤1 уровень серого (округление RGB→L и билинейная фильтрация). int8 dynamic
(4.7 МБ) не теряет точность, int8 static — теряет.
