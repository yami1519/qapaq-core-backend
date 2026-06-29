from pydantic import BaseModel

class ScoringIn(BaseModel):
    codcliente: str
    montosolicitud: float
    plazo: int                 # meses
    codtipocredito: str        # ME, PE, CO, HI
    montoingresoneto: float
    codactividadeconomica: str
    codasesor: str

class ScoringOut(BaseModel):
    codcliente: str
    score: float               # 0 - 100
    decision: str              # APROBADO / OBSERVADO / RECHAZADO
    resultado: str             # APROBABLE / OBSERVADO / NO APTO
    semaforo: str              # VERDE / AMARILLO / ROJO
    tea_sugerida: float        # en porcentaje
    tem_sugerida: float        # en porcentaje
    cuota_estimada: float      # S/
    rds: float | None          # cuota_estimada / ingreso neto, en porcentaje
    observaciones: list[str]
    detalle_score: dict
