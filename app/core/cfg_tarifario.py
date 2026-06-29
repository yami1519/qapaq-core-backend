"""Tarifarios oficiales para los productos Qapaq vigentes desde 2026-05-01."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TarifarioCredito:
    producto: str
    nombre_tarifario: str
    tea_minima: float
    tea_maxima: float
    tea_usada: float
    moratoria_nominal_anual: float
    itf: float
    vigencia_desde: str
    fuente: str


NEGOCIO = TarifarioCredito(
    producto="NEGOCIO",
    nombre_tarifario="Microempresa - PYME",
    tea_minima=40.99,
    tea_maxima=114.13,
    tea_usada=40.99,
    moratoria_nominal_anual=17.11,
    itf=0.005,
    vigencia_desde="2026-05-01",
    fuente="Tarifario Prestamo Microempresa",
)

PERSONAL = TarifarioCredito(
    producto="PERSONAL",
    nombre_tarifario="Consumo",
    tea_minima=97.99,
    tea_maxima=114.13,
    tea_usada=97.99,
    moratoria_nominal_anual=17.11,
    itf=0.005,
    vigencia_desde="2026-05-01",
    fuente="Tarifario Prestamo Consumo",
)

TARIFARIOS = {
    "NEGOCIO": NEGOCIO,
    "PERSONAL": PERSONAL,
}

_ALIAS_PRODUCTO = {
    "ME": "NEGOCIO",
    "PE": "NEGOCIO",
    "01": "NEGOCIO",
    "02": "NEGOCIO",
    "CO": "PERSONAL",
    "03": "PERSONAL",
}


def obtener_tarifario(codtipocredito: str | None) -> TarifarioCredito:
    codigo = (codtipocredito or "").strip().upper()
    return TARIFARIOS[_ALIAS_PRODUCTO.get(codigo, "NEGOCIO")]


def tea_a_tem(tea: float) -> float:
    # Conversion TEA a TEM usando base 360 dias del tarifario (30/360).
    return (1 + tea / 100) ** (30 / 360) - 1


def cuota_francesa(principal: float, plazo: int, tea: float) -> float:
    tem = tea_a_tem(tea)
    if tem <= 0:
        return principal / plazo
    return principal * tem / (1 - (1 + tem) ** (-plazo))


def generar_cronograma_frances(principal: float, plazo: int, tea: float) -> list[dict]:
    plazo = max(int(plazo or 1), 1)
    saldo = round(float(principal or 0), 2)
    tem = tea_a_tem(tea)
    cuota_base = cuota_francesa(saldo, plazo, tea)
    cuotas = []

    for nro in range(1, plazo + 1):
        interes = round(saldo * tem, 2)
        if nro == plazo:
            capital = saldo
            cuota = round(capital + interes, 2)
            saldo_final = 0.0
        else:
            cuota = round(cuota_base, 2)
            capital = round(cuota - interes, 2)
            saldo_final = round(max(0.0, saldo - capital), 2)

        cuotas.append({
            "nrocuota": nro,
            "cuota": cuota,
            "capital": capital,
            "interes": interes,
            "saldo": saldo_final,
        })
        saldo = saldo_final

    return cuotas
