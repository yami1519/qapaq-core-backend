import unittest

from app.core import cfg_tarifario
from app.services import svc_reglas_credito


class ScoringReglasCreditoTest(unittest.TestCase):
    def evaluar(self, monto, plazo, ingreso):
        observaciones = []
        resultado = svc_reglas_credito.decidir_resultado_credito(
            score_total=97,
            monto=monto,
            plazo=plazo,
            ingreso_neto=ingreso,
            tea_minima=cfg_tarifario.NEGOCIO.tea_minima,
            tea_media=cfg_tarifario.NEGOCIO.tea_usada,
            tea_maxima=cfg_tarifario.NEGOCIO.tea_maxima,
            observaciones=observaciones,
        )
        resultado["observaciones"] = observaciones
        return resultado

    def test_tea_porcentual_se_convierte_a_tem(self):
        esperado = (1 + 0.41) ** (1 / 12) - 1
        self.assertAlmostEqual(cfg_tarifario.tea_a_tem(41.0), esperado, places=10)

    def test_ingreso_extremadamente_bajo_es_no_apto(self):
        res = self.evaluar(monto=8000, plazo=6, ingreso=1)

        self.assertEqual(res["semaforo"], "ROJO")
        self.assertEqual(res["resultado"], "NO APTO")
        self.assertGreater(res["rds"], 50)
        self.assertIn("Cuota supera el 50% del ingreso neto mensual — riesgo crítico.", res["observaciones"])

    def test_monto_alto_sin_capacidad_es_no_apto(self):
        res = self.evaluar(monto=500000, plazo=48, ingreso=1500)

        self.assertEqual(res["semaforo"], "ROJO")
        self.assertEqual(res["resultado"], "NO APTO")
        self.assertGreater(res["cuota_estimada"], 1500)
        self.assertGreater(res["rds"], 50)

    def test_capacidad_razonable_no_es_rojo(self):
        res = self.evaluar(monto=5000, plazo=48, ingreso=1500)

        self.assertLessEqual(res["rds"], 35)
        self.assertIn(res["semaforo"], ("VERDE", "AMARILLO"))
        self.assertNotEqual(res["resultado"], "NO APTO")

    def test_ingreso_cero_es_no_apto_sin_rds_infinito(self):
        res = self.evaluar(monto=8000, plazo=6, ingreso=0)

        self.assertEqual(res["semaforo"], "ROJO")
        self.assertEqual(res["resultado"], "NO APTO")
        self.assertIsNone(res["rds"])
        self.assertIn("Ingreso neto mensual inválido.", res["observaciones"])


if __name__ == "__main__":
    unittest.main()
