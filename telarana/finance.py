from datetime import date

from .database import get_month_data, history

def money(value):
    return "$" + f"{value:,.0f}".replace(",", ".")

def status(result):
    if result > 0.005: return "POSITIVO"
    if result < -0.005: return "NEGATIVO"
    return "NEUTRO"

def committed_ratio(data):
    income = data["income"]
    obligations = data["obligations"]
    if income <= 0:
        return 1.0 if obligations > 0 else 0.0
    return min(obligations / income, 1.0)

def streak_info():
    """Cuenta meses consecutivos con datos; meses vacíos no generan rachas."""
    rows = history(36)
    current = None
    count = 0
    for _, income, obligations, result in reversed(rows):
        if income == 0 and obligations == 0:
            break
        state = status(result)
        if current is None:
            current, count = state, 1
        elif state == current:
            count += 1
        else:
            break
    return current or "SIN DATOS", count

def projection(month, data, extra_obligation=0):
    return data["income"] - data["obligations"] - extra_obligation


def streak_days(count):
    """Días de racha activa. La racha se activa con 3 meses consecutivos."""
    if count < 3:
        return 0
    today = date.today()
    total = today.year * 12 + today.month - 1 - (count - 1)
    start = date(total // 12, total % 12 + 1, 1)
    return (today - start).days + 1

def alerts(data, ratio):
    """Alertas del periodo; lista vacía = todo en orden."""
    found = []
    if data["result"] < -0.005:
        found.append("Tus obligaciones superan tus ingresos en este periodo.")
    elif data["income"] > 0 and ratio >= 0.9:
        found.append(f"Tus obligaciones ya usan el {ratio * 100:.0f}% de tus ingresos.")
    return found
