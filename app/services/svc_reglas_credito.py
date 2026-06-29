from math import isfinite

from app.core import cfg_tarifario


def agregar_observacion(observaciones: list[str], texto: str) -> None:
    if texto not in observaciones:
        observaciones.append(texto)


def ingreso_es_valido(ingreso: float) -> bool:
    try:
        ingreso_val = float(ingreso)
    except (TypeError, ValueError):
        return False
    return ingreso_val > 0 and isfinite(ingreso_val)


def decidir_resultado_credito(
    *,
    score_total: float,
    monto: float,
    plazo: int,
    ingreso_neto: float,
    tea_minima: float,
    tea_media: float,
    tea_maxima: float,
    observaciones: list[str],
) -> dict:
    cuota_referencia = cfg_tarifario.cuota_francesa(monto, plazo, tea_media)
    ingreso_valido = ingreso_es_valido(ingreso_neto)
    rds_referencia = cuota_referencia / ingreso_neto if ingreso_valido else None

    if not ingreso_valido:
        semaforo = "ROJO"
        resultado = "NO APTO"
        decision = "RECHAZADO"
        tea_sugerida = tea_maxima
        agregar_observacion(observaciones, "Ingreso neto mensual inválido.")
        agregar_observacion(observaciones, "Cliente no apto para aprobación automática.")
    elif rds_referencia > 0.50:
        semaforo = "ROJO"
        resultado = "NO APTO"
        decision = "RECHAZADO"
        tea_sugerida = tea_maxima
        agregar_observacion(
            observaciones,
            "Cuota supera el 50% del ingreso neto mensual — riesgo crítico.",
        )
        agregar_observacion(observaciones, "Cliente no apto para aprobación automática.")
    elif score_total >= 75 and rds_referencia <= 0.35:
        semaforo = "VERDE"
        resultado = "APROBABLE"
        decision = "APROBADO"
        tea_sugerida = tea_minima
        agregar_observacion(observaciones, "Capacidad de pago adecuada.")
    elif score_total >= 50 or (0.35 < rds_referencia <= 0.50):
        semaforo = "AMARILLO"
        resultado = "OBSERVADO"
        decision = "OBSERVADO"
        tea_sugerida = tea_media
        agregar_observacion(observaciones, "Requiere aprobación de jefe de agencia.")
    else:
        semaforo = "ROJO"
        resultado = "NO APTO"
        decision = "RECHAZADO"
        tea_sugerida = tea_maxima
        agregar_observacion(observaciones, "Cliente no apto para aprobación automática.")

    cuota_final = cfg_tarifario.cuota_francesa(monto, plazo, tea_sugerida)
    rds_final = cuota_final / ingreso_neto if ingreso_valido else None
    tem_sugerida = cfg_tarifario.tea_a_tem(tea_sugerida) * 100

    return {
        "decision": decision,
        "resultado": resultado,
        "semaforo": semaforo,
        "tea_sugerida": tea_sugerida,
        "tem_sugerida": round(tem_sugerida, 4),
        "cuota_estimada": round(cuota_final, 2),
        "rds": round(rds_final * 100, 2) if rds_final is not None else None,
    }
