# Індекс діаграм — SportPredict AI

Всі діаграми знаходяться у папці `docs/diagrams/` у форматі Markdown + Mermaid.

| Файл | Тип діаграми | Зміст |
|------|-------------|-------|
| [use_case.md](use_case.md) | UML Use Case | Прецеденти системи для 3 ролей (Користувач, Аналітик, Адмін) |
| [sequence_diagrams.md](sequence_diagrams.md) | UML Sequence × 2 | AI-прогнозування + Live SSE-трансляція |
| [class_diagram.md](class_diagram.md) | UML Class | 15 ORM-класів (SQLAlchemy моделі) |
| [dfd.md](dfd.md) | DFD (рівень 0 + 1) | Потоки даних: користувач ↔ система ↔ ESPN ↔ LLM |
| [er_diagram.md](er_diagram.md) | ER (IDEF1X) | Реляційна схема БД (15 таблиць) |
| [architecture.md](architecture.md) | Архітектура + IDEF0 | Docker-стек + декомпозиція прогнозування |
| [deployment.md](deployment.md) | Deployment + State | Docker Compose розгортання + стани матчу |

## Як переглянути

Mermaid-діаграми відображаються:
- Автоматично на **GitHub** (рендерить Mermaid у Markdown)
- У **VS Code** з розширенням _Markdown Preview Mermaid Support_
- На сайті **mermaid.live** (онлайн-редактор)
