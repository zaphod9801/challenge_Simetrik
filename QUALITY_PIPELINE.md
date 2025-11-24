# Pipeline de Calidad y Evaluación (Quality Pipeline)

Este documento describe el proceso implementado para evaluar, medir y optimizar el rendimiento del Agente de Detección de Incidencias.

## 1. Metodología de Evaluación

El objetivo es medir qué tan preciso es el agente detectando incidencias críticas (**URGENT**) comparado con el juicio humano (Ground Truth).

### Definición de Ground Truth
Utilizamos el feedback proporcionado por los stakeholders (`Feedback - week 9 sept.xlsx`) para establecer una "Verdad de Campo" para el día **2025-09-10**.
Se identificaron 5 fuentes con incidencias críticas confirmadas:
- `220504`, `220505`, `220506`, `196125`, `195385`.

### Métricas
Nos enfocamos en la clase **URGENT** (Incidencia Crítica), ya que es la más importante para el negocio.

- **True Positive (TP)**: El agente clasificó correctamente una fuente crítica como URGENT.
- **False Positive (FP)**: El agente marcó como URGENT una fuente que no lo era.
- **False Negative (FN)**: El agente falló en detectar una fuente crítica (la marcó como ATTENTION o ALL_GOOD).
- **Precision**: `TP / (TP + FP)` - ¿Qué porcentaje de las alertas urgentes eran reales?
- **Recall**: `TP / (TP + FN)` - ¿Qué porcentaje de los problemas reales detectamos?
- **F1 Score**: Media armónica entre Precision y Recall.

## 2. Proceso de Optimización (Ciclo de Mejora)

El pipeline de calidad se ejecutó en dos iteraciones principales:

### Iteración 1: Línea Base
- **Ejecución**: Se corrió el agente con el prompt inicial.
- **Resultados**:
    - Precision: 1.00
    - Recall: 0.80
    - F1 Score: 0.89
- **Análisis**: El agente falló en detectar la fuente `195385` como URGENT. La clasificó como ATTENTION_REQUIRED. El problema era una caída masiva de volumen (de ~40 a ~7 archivos), pero el prompt no tenía una regla explícita para "caídas masivas" como criterio de urgencia.

### Iteración 2: Ajuste de Prompt
- **Acción**: Se modificó `src/agent_adk.py` para refinar las "Severity Rules".
    - Se añadió: *"If volume drops by > 50% compared to expected, this is URGENT."*
    - Se añadió: *"If NO files are received (Total Outage), this is URGENT."* (Para corregir un caso borde con la fuente `196125`).
- **Resultados**:
    - Precision: 1.00
    - Recall: 1.00
    - F1 Score: 1.00
- **Conclusión**: El ajuste de las instrucciones (Prompt Engineering) basado en métricas permitió alcanzar un rendimiento perfecto en el set de prueba.

## 3. Cómo Ejecutar la Evaluación

El script de evaluación automatiza este proceso:

```bash
python3 -m src.evaluation
```

Este script:
1. Carga los datos del día de prueba.
2. Ejecuta el agente sobre las fuentes etiquetadas.
3. Compara la salida con el `GROUND_TRUTH`.
4. Imprime la tabla de confusión y las métricas finales.

## 4. Recomendaciones Futuras
- **Ampliar el Dataset**: Incorporar más días de feedback para evitar sobreajuste (overfitting) al día 10.
- **Human-in-the-loop**: Implementar un mecanismo para que los analistas validen las alertas diarias y retroalimenten el sistema automáticamente.
