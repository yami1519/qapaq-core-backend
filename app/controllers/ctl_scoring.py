from sqlalchemy.orm import Session
from app.core import cfg_tarifario
from app.repositories import rep_clientes, rep_creditos
from app.services import svc_reglas_credito

# Tabla de referencia mantenida por compatibilidad con imports existentes.
TEA_POR_TIPO = {
    "ME": {
        "min": cfg_tarifario.NEGOCIO.tea_minima,
        "mid": cfg_tarifario.NEGOCIO.tea_usada,
        "max": cfg_tarifario.NEGOCIO.tea_maxima,
    },
    "PE": {
        "min": cfg_tarifario.NEGOCIO.tea_minima,
        "mid": cfg_tarifario.NEGOCIO.tea_usada,
        "max": cfg_tarifario.NEGOCIO.tea_maxima,
    },
    "CO": {
        "min": cfg_tarifario.PERSONAL.tea_minima,
        "mid": cfg_tarifario.PERSONAL.tea_usada,
        "max": cfg_tarifario.PERSONAL.tea_maxima,
    },
}

SECTORES_RIESGO = {
    # bajo riesgo
    "4711": 20, "4721": 20, "4731": 18, "5610": 18,
    "6810": 15, "8511": 15,
    # riesgo medio
    "4921": 12, "4923": 12, "0111": 10, "0112": 10,
    # riesgo alto
    "6201": 8,  "5510": 8,
}

def calcular_score(
    codcliente: str,
    montosolicitud: float,
    plazo: int,
    codtipocredito: str,
    montoingresoneto: float,
    codactividadeconomica: str,
    db: Session
) -> dict:

    observaciones = []
    detalle = {}

    def add_observacion(texto: str) -> None:
        svc_reglas_credito.agregar_observacion(observaciones, texto)

    # ── 1. CAPACIDAD DE PAGO (40 pts) ──────────────────────────
    tarifario = cfg_tarifario.obtener_tarifario(codtipocredito)
    tea_tipo = TEA_POR_TIPO.get(
        codtipocredito, {"min": tarifario.tea_minima, "mid": tarifario.tea_usada, "max": tarifario.tea_maxima}
    )
    tea_ref = tea_tipo["mid"]
    cuota = cfg_tarifario.cuota_francesa(montosolicitud, plazo, tea_ref)
    ingreso_valido = svc_reglas_credito.ingreso_es_valido(montoingresoneto)
    ratio_cuota_ingreso = cuota / montoingresoneto if ingreso_valido else None

    if not ingreso_valido:
        score_capacidad = 0
        add_observacion("Ingreso neto mensual inválido.")
    elif ratio_cuota_ingreso <= 0.30:
        score_capacidad = 40
    elif ratio_cuota_ingreso <= 0.40:
        score_capacidad = 30
    elif ratio_cuota_ingreso <= 0.50:
        score_capacidad = 18
        add_observacion("Cuota representa más del 40% del ingreso neto.")
    else:
        score_capacidad = 5
        add_observacion("Cuota supera el 50% del ingreso neto mensual — riesgo crítico.")

    detalle["capacidad_pago"] = {
        "cuota_estimada": round(cuota, 2),
        "ratio_cuota_ingreso": round(ratio_cuota_ingreso * 100, 2) if ratio_cuota_ingreso is not None else None,
        "puntaje": score_capacidad
    }

    # ── 2. HISTORIAL EN BD (30 pts) ────────────────────────────
    cliente = rep_clientes.get_by_cod(db, codcliente)
    score_historial = 0

    if not cliente:
        score_historial = 10
        add_observacion("Cliente no registrado en la institución.")
    else:
        tiene_vencido = rep_creditos.tiene_mala_calificacion(db, cliente.pkcliente)
        if tiene_vencido:
            score_historial = 5
            add_observacion("Cliente tiene créditos con calificación Deficiente, Dudoso o Pérdida.")
        else:
            score_historial = 30

    detalle["historial"] = {"puntaje": score_historial}

    # ── 3. SECTOR ECONÓMICO (20 pts) ───────────────────────────
    score_sector = SECTORES_RIESGO.get(codactividadeconomica, 10)
    detalle["sector_economico"] = {
        "codactividad": codactividadeconomica,
        "puntaje": score_sector
    }

    # ── 4. PLAZO (10 pts) ──────────────────────────────────────
    if plazo <= 24:
        score_plazo = 10
    elif plazo <= 48:
        score_plazo = 7
    elif plazo <= 120:
        score_plazo = 4
    else:
        score_plazo = 2
        add_observacion("Plazo mayor a 10 años incrementa el riesgo.")

    detalle["plazo"] = {"meses": plazo, "puntaje": score_plazo}

    # ── SCORE TOTAL ─────────────────────────────────────────────
    score_total = score_capacidad + score_historial + score_sector + score_plazo
    detalle["score_total"] = score_total

    # ── DECISIÓN ────────────────────────────────────────────────
    decision_credito = svc_reglas_credito.decidir_resultado_credito(
        score_total=score_total,
        monto=montosolicitud,
        plazo=plazo,
        ingreso_neto=montoingresoneto,
        tea_minima=tea_tipo["min"],
        tea_media=tea_tipo["mid"],
        tea_maxima=tea_tipo["max"],
        observaciones=observaciones,
    )

    return {
        "codcliente":      codcliente,
        "score":           round(score_total, 2),
        "observaciones":   observaciones,
        "detalle_score":   detalle,
        **decision_credito,
    }
