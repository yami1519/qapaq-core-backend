"""
Repositorio de evaluación y desembolso de solicitudes — MPR-003-CRE (actividades 11, 16, 45-48).

- registrar_ingreso: fuente de ingreso del cliente (fclientefuenteingreso).
- registrar_evaluacion: cabecera (devaluacion) + detalle (fevalconsumo|fevalmicroactivo).
- desembolsar: crea la cuenta de crédito (dcuentacredito) + movimiento de desembolso
  (foperaciones) y marca la solicitud como Desembolsada.
"""
from datetime import datetime
from calendar import monthrange
from sqlalchemy.orm import Session
from sqlalchemy import text

PERIODO = 202512


def _add_months(fecha, months: int):
    month = fecha.month - 1 + months
    year = fecha.year + month // 12
    month = month % 12 + 1
    day = min(fecha.day, monthrange(year, month)[1])
    return fecha.replace(year=year, month=month, day=day)


def _cuenta_destino_desembolso(db: Session, pkcliente: int):
    """
    Selecciona una cuenta de ahorro activa existente para recibir el desembolso.
    Prioriza cuentas cuyo código empiece con AH y, dentro de cada grupo, la menor PK.
    """
    return db.execute(text("""
        SELECT ca.pkcuentaahorro,
               ca.codcuentaahorro,
               f.periododia
        FROM dcuentaahorro ca
        JOIN fcuentaahorro f
          ON f.pkcuentaahorro = ca.pkcuentaahorro
         AND f.periododia = (
             SELECT MAX(f2.periododia)
             FROM fcuentaahorro f2
             WHERE f2.pkcuentaahorro = ca.pkcuentaahorro
         )
        JOIN destadocuenta ec ON ec.pkestadocuenta = f.pkestadocuenta
        WHERE ca.pkcliente = :pkcliente
          AND f.pkcliente = :pkcliente
          AND TRIM(ec.codestadocuenta) = '01'
          AND ec.estado = '1'
        ORDER BY
          CASE WHEN UPPER(TRIM(ca.codcuentaahorro)) LIKE 'AH%' THEN 0 ELSE 1 END,
          ca.pkcuentaahorro
        LIMIT 1
    """), {"pkcliente": pkcliente}).fetchone()


def _abonar_cuenta_destino(db: Session, pkcuentaahorro: int, periododia: int, monto: float) -> None:
    """Abona el monto en el snapshot existente elegido; no crea cuentas ni nuevos snapshots."""
    res = db.execute(text("""
        UPDATE fcuentaahorro
        SET montosaldocapitaltotal = montosaldocapitaltotal + :monto,
            montosaldodisponible_ac = CASE
                WHEN flag_ac = 'S' THEN montosaldodisponible_ac + :monto
                ELSE montosaldodisponible_ac
            END,
            montosaldocontable_ac = CASE
                WHEN flag_ac = 'S' THEN montosaldocontable_ac + :monto
                ELSE montosaldocontable_ac
            END,
            fecultactualizacion = NOW()
        WHERE pkcuentaahorro = :pkcuentaahorro
          AND periododia = :periododia
    """), {
        "pkcuentaahorro": pkcuentaahorro,
        "periododia": periododia,
        "monto": monto,
    })
    if res.rowcount != 1:
        raise ValueError("No se pudo abonar el desembolso en la cuenta de ahorros destino.")


def registrar_ingreso(db: Session, pkcliente: int, *, tipo: str, monto: float,
                      nombre_empresa: str = None) -> dict:
    # PK compuesta (pkcliente, periodomes): upsert para que sea idempotente.
    db.execute(text("""
        INSERT INTO fclientefuenteingreso
            (pkcliente, periodomes, tipofuenteingreso, montofuenteingreso,
             codrelacion, nombreempresa, fecultactualizacion)
        VALUES (:pk, :per, :tipo, :monto, 'T', :emp, NOW())
        ON CONFLICT (pkcliente, periodomes) DO UPDATE
            SET tipofuenteingreso = EXCLUDED.tipofuenteingreso,
                montofuenteingreso = EXCLUDED.montofuenteingreso,
                nombreempresa = EXCLUDED.nombreempresa,
                fecultactualizacion = NOW()
    """), {"pk": pkcliente, "per": PERIODO, "tipo": tipo[:2],
           "monto": monto, "emp": nombre_empresa})
    db.commit()
    return {"pkcliente": pkcliente, "tipo": tipo, "monto": monto}


def registrar_evaluacion(db: Session, codsolicitud: str, *, es_microempresa: bool,
                         ingreso: float, gasto_familiar: float,
                         monto_solicitud: float = 0.0,
                         fortaleza: str = "", debilidad: str = "") -> dict:
    """Crea/actualiza la evaluación de la solicitud (cabecera + detalle según tipo)."""
    # evita duplicar: si ya hay evaluación para la solicitud, la retorna
    ya = db.execute(text("SELECT pkevaluacion FROM devaluacion WHERE codsolicitud=:c"),
                    {"c": codsolicitud}).scalar()
    if ya:
        return {"codsolicitud": codsolicitud, "pkevaluacion": ya, "creada": False}

    excedente = round(ingreso - gasto_familiar, 2)
    row = db.execute(text("""
        INSERT INTO devaluacion
            (nroevaluacion, valorexcedentecredito, tipoevaluacion, codsolicitud, fecultactualizacion)
        VALUES ('EV-' || :c, :exc, :tipo, :c, NOW())
        RETURNING pkevaluacion
    """), {"c": codsolicitud, "exc": excedente, "tipo": "ME" if es_microempresa else "CO"}).fetchone()
    pkeval = row.pkevaluacion

    if es_microempresa:
        db.execute(text("""
            INSERT INTO fevalmicroactivo
                (pkevaluacion, nroreg, montoactivodisponible, montoactivoinventario,
                 montoactivofijo, montogastofamiliar, fecultactualizacion)
            VALUES (:pk, 1, :disp, :inv, :fijo, :gf, NOW())
        """), {"pk": pkeval, "disp": round(monto_solicitud*0.20, 2),
               "inv": round(monto_solicitud*0.50, 2), "fijo": round(monto_solicitud*0.80, 2),
               "gf": gasto_familiar})
    else:
        db.execute(text("""
            INSERT INTO fevalconsumo
                (pkevaluacion, monto, montogastofamiliar, codtipoingreso,
                 fortalezaevaluacion, debilidadevaluacion, fecultactualizacion)
            VALUES (:pk, :monto, :gf, 'D', :fz, :db, NOW())
        """), {"pk": pkeval, "monto": ingreso, "gf": gasto_familiar,
               "fz": fortaleza or "Ingreso estable", "db": debilidad or "Sin garantía real"})
    db.commit()
    return {"codsolicitud": codsolicitud, "pkevaluacion": pkeval, "excedente": excedente, "creada": True}


def desembolsar(db: Session, sol) -> dict:
    """
    Crea la cuenta de crédito y el movimiento de desembolso para una solicitud APROBADA.
    `sol` es la fila de rep_solicitudes.obtener (debe tener pksolicitud, pkcliente, monto, etc.).
    """
    monto = float(sol.montoaprobadocredito or sol.montosolicitudcredito or 0)
    plazo = int(
        getattr(sol, "nrocuotaaprobado", None)
        or getattr(sol, "plazoaprobadocredito", None)
        or sol.nrocuotasolicitud
        or sol.plazosolicitudcredito
        or 1
    )
    plazo = max(plazo, 1)

    existente = db.execute(text("""
        SELECT cc.codcuentacredito, f.montocapitaldesembolsado
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        WHERE f.pksolicitud = :pksol
        ORDER BY f.periodomes DESC
        LIMIT 1
    """), {"pksol": sol.pksolicitud}).fetchone()
    if existente:
        return {
            "codcuentacredito": existente.codcuentacredito,
            "monto_desembolsado": float(existente.montocapitaldesembolsado or 0),
            "ya_existia": True,
        }

    cuenta_destino = _cuenta_destino_desembolso(db, sol.pkcliente)
    if cuenta_destino is None:
        raise ValueError("El cliente no tiene una cuenta de ahorros activa para recibir el desembolso.")

    sol_data = db.execute(text("""
        SELECT s.pkproducto, s.pkagencia, s.pkasesor, s.pkmoneda
        FROM dsolicitud s
        WHERE s.pksolicitud = :pksol
        LIMIT 1
    """), {"pksol": sol.pksolicitud}).fetchone()

    # genera la cuenta de crédito (codigo derivado del pk por secuencia)
    cc = db.execute(text("""
        INSERT INTO dcuentacredito (pkcuentacredito, codcuentacredito, pkcliente, nrocronograma, fecultactualizacion)
        VALUES (nextval('dcuentacredito_pkcuentacredito_seq'),
                'CRD' || LPAD(currval('dcuentacredito_pkcuentacredito_seq')::text, 7, '0'),
                :pkcli, 1, NOW())
        RETURNING pkcuentacredito, codcuentacredito
    """), {"pkcli": sol.pkcliente}).fetchone()

    # catálogos para el movimiento de desembolso y la cartera visible en Homebanking.
    cat = db.execute(text("""
        SELECT (SELECT pkconceptooperacion FROM dconceptooperacion WHERE codconceptooperacion='DCAP') con,
               (SELECT pktipooperacion FROM dtipooperacion WHERE codtipooperacion='CRE') tipo,
               (SELECT pkmediopago FROM dmediopago WHERE codmediopago='WEB') medio,
               (SELECT pkcanaltransaccional FROM dcanaltransaccional WHERE codcanaltransaccional='WEB') canal,
               (SELECT pkcondicioncontable FROM dcondicioncontable WHERE codcondicioncontable='01') cond,
               (SELECT pkmoneda FROM dmoneda ORDER BY pkmoneda LIMIT 1) mon,
               (SELECT MIN(pkproducto) FROM dproducto) prod,
               (SELECT MIN(pkagencia) FROM dagencia) ag,
               (SELECT MIN(pkasesor) FROM dasesor) asesor,
               COALESCE((SELECT pkestadocredito FROM destadocredito WHERE codestadocredito='01' ORDER BY pkestadocredito LIMIT 1),
                        (SELECT MIN(pkestadocredito) FROM destadocredito)) est,
               COALESCE((SELECT pkcalificacioncrediticia FROM dcalificacioncrediticia WHERE codcalificacioncrediticia='0' ORDER BY pkcalificacioncrediticia LIMIT 1),
                        (SELECT MIN(pkcalificacioncrediticia) FROM dcalificacioncrediticia)) cal
    """)).fetchone()

    hoy = datetime.utcnow()
    fecha_desembolso = hoy.date()
    pd = int(hoy.strftime("%Y%m%d"))
    pkproducto = sol_data.pkproducto or cat.prod
    pkagencia = sol_data.pkagencia or cat.ag
    pkasesor = sol_data.pkasesor or cat.asesor
    pkmoneda = sol_data.pkmoneda or cat.mon
    cuota = round(monto / plazo, 4)

    db.execute(text("""
        INSERT INTO fagcuentacredito (
            periodomes, pkcuentacredito, pksolicitud, pkestadocredito,
            nrocuotas, nrodias, nrodiasgracias,
            montoaprobadocredito, montocapitaldesembolsado,
            pkproducto, pkmoneda, tasainterescompensatoria, tasainteresmoratoria,
            fechageneracioncredito, fechadesembolsocredito,
            pkcliente, pkcondicioncontable, pkcalificacioncrediticiainterna,
            montocapitalinicio, montosaldocapital, car_vig_capital, montosaldocliente,
            pkagencia, pkasesor, fecultactualizacion
        ) VALUES (
            :per, :pkcc, :pksol, :est,
            :plazo, 0, 0,
            :monto, :monto,
            :prod, :mon, 0, 0,
            :fec, :fec,
            :pkcli, :cond, :cal,
            :monto, :monto, :monto, :monto,
            :ag, :asesor, NOW()
        )
        ON CONFLICT (periodomes, pkcuentacredito) DO NOTHING
    """), {
        "per": PERIODO, "pkcc": cc.pkcuentacredito, "pksol": sol.pksolicitud,
        "est": cat.est, "plazo": plazo, "monto": monto,
        "prod": pkproducto, "mon": pkmoneda, "fec": fecha_desembolso,
        "pkcli": sol.pkcliente, "cond": cat.cond, "cal": cat.cal,
        "ag": pkagencia, "asesor": pkasesor,
    })

    saldo = monto
    for nro in range(1, plazo + 1):
        vencimiento = _add_months(fecha_desembolso, nro)
        saldo = max(0, round(saldo - cuota, 4))
        db.execute(text("""
            INSERT INTO fplanpagomes (
                periodomes, pkcuentacredito, codplanpago, nrocuota,
                pksolicitud, pkestadocredito, pkproducto, pkmoneda,
                pkcliente, pkcondicioncontable, pkcalificacioncrediticiainterna,
                pkagencia, pkasesor, codestadocuota, fechavencimientopagocuota,
                montocuota, montosaldo, montosaldocapital, montocapitalprogramado,
                montocapitaldesembolsado, fecultactualizacion
            ) VALUES (
                :per, :pkcc, :codplan, :nro,
                :pksol, :est, :prod, :mon,
                :pkcli, :cond, :cal,
                :ag, :asesor, 'PE', :vence,
                :cuota, :saldo, :saldo, :cuota,
                :monto, NOW()
            )
            ON CONFLICT (periodomes, pkcuentacredito, nrocuota) DO NOTHING
        """), {
            "per": PERIODO, "pkcc": cc.pkcuentacredito,
            "codplan": f"PP{cc.pkcuentacredito}-{nro}"[:15],
            "nro": nro, "pksol": sol.pksolicitud, "est": cat.est,
            "prod": pkproducto, "mon": pkmoneda, "pkcli": sol.pkcliente,
            "cond": cat.cond, "cal": cat.cal, "ag": pkagencia,
            "asesor": pkasesor, "vence": vencimiento, "cuota": cuota,
            "saldo": saldo, "monto": monto,
        })

    db.execute(text("""
        INSERT INTO foperaciones
            (codtipkar, codkardex, pkcuentacredito, pkcuentaahorro, pkconceptooperacion, pktipooperacion,
             pkmediopago, pkcanaltransaccional, pkmoneda, pkcondicioncontable, pkproducto,
             pkagenciaorigen, montooperacion, montopagoconcepto, codtipoegresoingreso,
             fechahoraoperacion, periododia, codusuope, fecultactualizacion)
        VALUES ('CR', 'DESEMB-' || :pkcc, :pkcc, :pkah, :con, :tipo, :medio, :canal, :mon, :cond, :prod,
                :ag, :monto, :monto, 'I', :fh, :pd, 'CORE', NOW())
    """), {"pkcc": cc.pkcuentacredito, "con": cat.con, "tipo": cat.tipo, "medio": cat.medio,
           "canal": cat.canal, "mon": pkmoneda, "cond": cat.cond, "prod": pkproducto,
           "ag": pkagencia, "monto": monto, "fh": hoy, "pd": pd,
           "pkah": cuenta_destino.pkcuentaahorro})
    _abonar_cuenta_destino(db, cuenta_destino.pkcuentaahorro, cuenta_destino.periododia, monto)
    db.commit()
    return {"codcuentacredito": cc.codcuentacredito, "monto_desembolsado": monto,
            "codcuentaahorro_destino": cuenta_destino.codcuentaahorro,
            "fecha": hoy.date().isoformat()}
