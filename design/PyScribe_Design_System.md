# PyScribe — Design System v1.0

Цель: привести интерфейс PyScribe к единой, спокойной IDE-системе в духе VS Code Workbench, без механического копирования интерфейса.

## 1. Основной принцип

Интерфейс должен выглядеть как единое приложение:

- один базовый фон;
- один набор размеров;
- одна типографическая шкала;
- одна система отступов;
- иконки одинакового визуального веса;
- минимум декоративных рамок;
- никаких случайных градиентов;
- никакого текста на плашках другого цвета без функциональной причины;
- акцентный цвет используется только для активных/интерактивных состояний.

Главная задача — визуальная иерархия, а не большое количество декоративных элементов.

---

# 2. Цветовая система

## Base

| Token | Hex | Назначение |
|---|---|---|
| `bg-app` | `#181818` | основной фон Workbench |
| `bg-editor` | `#1E1E1E` | область редактора |
| `bg-sidebar` | `#181818` | Explorer / Search / Git |
| `bg-activity` | `#181818` | Activity Bar |
| `bg-panel` | `#181818` | Terminal / Output / Problems |
| `bg-input` | `#242424` | поля ввода |
| `bg-hover` | `#2A2D2E` | hover |
| `bg-active` | `#37373D` | активный элемент |
| `bg-selection` | `#264F78` | выделение текста/строки |
| `border` | `#2B2B2B` | тонкие разделители |
| `border-focus` | `#0078D4` | focus |
| `accent` | `#0078D4` | основной акцент |
| `accent-hover` | `#1A8AD8` | hover акцента |
| `text-primary` | `#D4D4D4` | основной текст |
| `text-secondary` | `#A8A8A8` | вторичный текст |
| `text-muted` | `#858585` | подписи/неактивный текст |
| `text-disabled` | `#5F5F5F` | disabled |
| `danger` | `#F14C4C` | ошибка/удаление |
| `warning` | `#CCA700` | предупреждение |
| `success` | `#89D185` | успешное состояние |
| `info` | `#75BEFF` | информационное состояние |

### Правило контраста

Текст никогда не должен иметь отдельную цветную плашку только ради дизайна.

Нормальная структура:

```text
[единый фон]
    текст
    текст
    [hover только при наведении]
```

Плохая структура:

```text
[цветной фон] текст
[другой фон]  текст
[ещё один фон] текст
```

---

# 3. Типографика

## UI

Приоритет шрифтов:

1. `Segoe UI`
2. `Inter`
3. `Arial`

Размеры:

| Назначение | Размер |
|---|---:|
| App title | 13 px |
| Menu | 12 px |
| Sidebar title | 11 px |
| Explorer item | 13 px |
| Tab | 13 px |
| Status bar | 12 px |
| Button | 12 px |
| Input | 13 px |
| Tooltip | 12 px |

Вес:

- обычный текст: 400;
- активный элемент: 400–500;
- заголовок панели: 500;
- не использовать жирный шрифт повсеместно.

## Editor

Приоритет:

1. `Cascadia Code`
2. `Consolas`
3. `JetBrains Mono`
4. `Courier New`

Размер: `13–14 px`.

Line height: около `1.45`.

---

# 4. Сетка и размеры

Используется базовая единица `4 px`.

Допустимые отступы:

```text
4
8
12
16
20
24
```

Не использовать случайные значения вроде:

```text
7
11
13
17
23
27
```

## Основные размеры

| Элемент | Размер |
|---|---:|
| Top Bar | 36 px |
| Activity Bar | 48 px |
| Sidebar | 260–300 px |
| Editor Tab | 36 px |
| Panel Header | 32 px |
| Status Bar | 22 px |
| Toolbar icon | 20 × 20 px |
| Activity icon | 20 × 20 px |
| Explorer icon | 16 × 16 px |
| Close icon | 16 × 16 px |
| Button height | 28 px |
| Input height | 28 px |

---

# 5. Top Bar

Top Bar должен быть максимально спокойным.

Структура:

```text
┌──────────────────────────────────────────────────────────────┐
│  [PyScribe icon] PyScribe   File Edit View Run Terminal Help │
│                                      Project: my-project     │
└──────────────────────────────────────────────────────────────┘
```

Высота: `36 px`.

Не использовать:

- большие кнопки;
- круглые кнопки;
- градиенты;
- декоративные рамки;
- крупные иконки.

---

# 6. Activity Bar

Ширина: `48 px`.

Каждый элемент:

```text
48 × 48 px
```

Иконка:

```text
20 × 20 px
```

Активное состояние:

- вертикальная полоска `2 px` слева;
- иконка `#FFFFFF`;
- фон слегка светлее базового.

Не использовать цветной квадрат за каждой иконкой.

Пример:

```text
│  Explorer
│  Search
│  Source Control
│  Run
│  Extensions
│
│
│  Settings
```

---

# 7. Sidebar

Ширина по умолчанию: `280 px`.

Заголовок:

- высота `32 px`;
- 11 px;
- uppercase допустим только для секционных заголовков;
- цвет `text-secondary`.

Explorer:

```text
EXPLORER

MY PROJECT
  ▾ src
      main.py
      editor.py
  ▸ tests
    README.md
```

Иконки файлов:

- 16×16;
- одинаковая геометрия;
- одинаковый baseline;
- цветовые акценты умеренные.

---

# 8. Editor

Фон: `#1E1E1E`.

Никаких дополнительных цветных прямоугольников под обычным текстом.

## Line numbers

```text
color: #858585
background: #1E1E1E
```

Активная строка:

```text
background: #232323
```

Selection:

```text
#264F78
```

Caret:

```text
#AEAFAD
```

---

# 9. Tabs

Вкладка:

```text
height: 36px
padding: 0 12px
```

Не использовать:

- круглые вкладки;
- большие скругления;
- градиенты;
- толстые рамки.

Активная вкладка:

- фон `#1E1E1E`;
- нижняя линия `2 px` accent.

Неактивная:

- фон `#181818`;
- текст `#A8A8A8`.

Modified:

```text
● filename.py
```

Закрытие:

- появляется при hover;
- 16×16;
- не занимает визуально половину вкладки.

---

# 10. Split Editor

Разделитель:

```text
1 px #2B2B2B
```

При hover:

```text
2 px #0078D4
```

Не использовать толстую рамку между редакторами.

Drop target при переносе вкладки:

```text
#264F78
```

с прозрачностью.

---

# 11. Bottom Panel

Высота по умолчанию:

```text
220–280 px
```

Вкладки:

```text
PROBLEMS
OUTPUT
TERMINAL
```

Не использовать кнопки старого типа:

```text
[ Clear ] [ Kill ] [ Run ]
```

Вместо этого:

```text
Terminal                     +  Split  Kill  ⋯
```

Иконки — 16 px.

---

# 12. Terminal

Фон:

```text
#181818
```

Текст:

```text
#D4D4D4
```

Prompt:

```text
#75BEFF
```

Командная строка должна выглядеть как часть IDE, а не как отдельное старое консольное окно.

---

# 13. Search

Поиск должен быть визуально простым:

```text
┌─────────────────────────────────┐
│ Search files...             ⚙   │
└─────────────────────────────────┘

2 results in 3 files

main.py
  12  def main():
  35  main()

editor.py
  81  main_window
```

Replace показывать только при раскрытии.

Не показывать бинарные файлы.

---

# 14. Context Menu

Контекстное меню — компактное.

Explorer:

```text
Open
Open With
──────────────
New File
New Folder
──────────────
Rename
Delete
──────────────
Copy Path
Reveal in File Manager
```

Редактор:

```text
Undo
Redo
──────────────
Cut
Copy
Paste
──────────────
Select All
──────────────
Command Palette
```

Не добавлять пункты, которые не реализованы.

---

# 15. Buttons

Основная кнопка:

```text
height: 28px
padding: 0 12px
background: #0078D4
border-radius: 2px
```

Secondary:

```text
background: #2A2D2E
border: 1px solid #3A3A3A
```

Не использовать:

- pill buttons;
- сильные тени;
- градиенты;
- большие скругления.

---

# 16. Icons

Все иконки должны использовать одну систему.

Размеры:

```text
Activity Bar: 20×20
Explorer:      16×16
Toolbar:       16×16
Menu:          16×16
Close:         16×16
```

Рекомендуемый стиль:

- monochrome;
- 1.5–2 px stroke;
- без emoji;
- без разноцветных квадратных фонов;
- одинаковая визуальная плотность.

---

# 17. Scrollbars

Ширина:

```text
10 px
```

Handle:

```text
#424242
```

Hover:

```text
#4F4F4F
```

Track:

```text
transparent
```

---

# 18. Status Bar

Высота:

```text
22 px
```

Содержимое:

```text
main.py     UTF-8     LF     Python     Git: main
```

Не делать Status Bar высокой.

---

# 19. Global QSS direction

Все Qt-виджеты должны наследовать одну систему:

```css
QWidget {
    background: #181818;
    color: #D4D4D4;
    font-family: "Segoe UI";
    font-size: 13px;
}

QPlainTextEdit,
QTextEdit {
    background: #1E1E1E;
    color: #D4D4D4;
    border: none;
}

QToolButton {
    background: transparent;
    border: none;
    padding: 4px 8px;
}

QToolButton:hover {
    background: #2A2D2E;
}

QLineEdit {
    background: #242424;
    color: #D4D4D4;
    border: 1px solid #3A3A3A;
    border-radius: 2px;
    padding: 4px 8px;
}

QLineEdit:focus {
    border: 1px solid #0078D4;
}
```

---

# 20. Главное правило

Если элемент нельзя объяснить с точки зрения:

1. функции;
2. иерархии;
3. состояния;
4. навигации;

его не должно быть в интерфейсе.

PyScribe должен выглядеть как IDE, а не как набор отдельно оформленных Qt-виджетов.
