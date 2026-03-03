"""
Serviço de atualização de cotas em batch.

Responsabilidade: atualizar valor_cota de todos os InfoFundo do banco
buscando dados da CVM (inf_diario_fi).

Fluxo:
1. Baixa inf_diario_fi do mês atual e do mês anterior
2. Para cada fundo com CNPJ, busca no mês atual primeiro, fallback mês anterior
3. Retorna resumo da operação
"""

from datetime import datetime, timedelta
import pandas as pd
from app.models.geld_models import InfoFundo
from app.services.extract_services import ExtractServices


class CotaUpdateService:

    def __init__(self, db):
        self.db = db
        self.extract = ExtractServices(db)

    # =========================================================================
    # MÉTODO PRINCIPAL
    # =========================================================================

    def atualizar_todas_cotas(self):
        """
        Atualiza valor_cota de todos os InfoFundo do banco.
        NÃO faz commit — responsabilidade da rota.

        Returns:
            dict: {
                'fi_atualizados': int,
                'sem_cnpj': int,
                'nao_encontrados': list[str],
                'total': int
            }
        """
        resultado = {
            'fi_atualizados': 0,
            'fii_atualizados': 0,
            'sem_cnpj': 0,
            'nao_encontrados': [],
            'total': 0
        }

        # Todos os fundos do banco
        fundos = self.db.query(InfoFundo).all()
        resultado['total'] = len(fundos)
        print(f"[COTAS] Iniciando atualização de {len(fundos)} fundos")

        # Separar fundos com e sem CNPJ
        fundos_com_cnpj = []
        for fundo in fundos:
            if not fundo.cnpj or fundo.cnpj.strip() == '':
                print(f"[COTAS] ⚠️  {fundo.nome_fundo[:40]}: sem CNPJ (pulado)")
                resultado['sem_cnpj'] += 1
            else:
                fundos_com_cnpj.append(fundo)

        if not fundos_com_cnpj:
            print("[COTAS] Nenhum fundo com CNPJ para atualizar")
            return resultado

        # Calcular meses a baixar
        mes_atual, mes_anterior = self._calcular_meses()

        print(f"\n[COTAS] Baixando dados FI...")
        df_atual    = self.extract.baixar_inf_diario_mes(*mes_atual)
        df_anterior = self.extract.baixar_inf_diario_mes(*mes_anterior)

        nao_encontrados_fi = []
        for fundo in fundos_com_cnpj:
            cnpj_norm = self._normalizar_cnpj(fundo.cnpj)
            nova_cota = self._buscar_cota(cnpj_norm, df_atual, df_anterior)

            if nova_cota is not None:
                self._atualizar_fundo(fundo, nova_cota)
                resultado['fi_atualizados'] += 1
            else:
                nao_encontrados_fi.append(fundo)

        print(f"[COTAS] FI: {resultado['fi_atualizados']} atualizados, "
              f"{len(nao_encontrados_fi)} não encontrados")

        # ── ETAPA 2: FIIs (informe mensal, para os não encontrados no FI) ─────
        if nao_encontrados_fi:
            print(f"\n[COTAS] Buscando {len(nao_encontrados_fi)} fundos no informe mensal FII...")
            ano_atual = mes_atual[0]
            ano_anterior = mes_anterior[0]

            df_fii = self.extract.baixar_inf_mensal_fii(ano_atual)
            # Se virou de ano (ex: janeiro), tenta também o ano anterior
            if df_fii.empty or ano_anterior != ano_atual:
                df_fii_anterior = self.extract.baixar_inf_mensal_fii(ano_anterior)
                if not df_fii_anterior.empty:
                    df_fii = pd.concat([df_fii, df_fii_anterior]).drop_duplicates()

            for fundo in nao_encontrados_fi:
                cnpj_norm = self._normalizar_cnpj(fundo.cnpj)
                nova_cota = self._buscar_cota_fii(cnpj_norm, df_fii)

                if nova_cota is not None:
                    self._atualizar_fundo(fundo, nova_cota)
                    resultado['fii_atualizados'] += 1
                else:
                    resultado['nao_encontrados'].append(fundo.nome_fundo)
                    print(f"[COTAS] ❌ {fundo.nome_fundo[:40]}: não encontrado em FI nem FII")

        print(f"\n[COTAS] Concluído — FI: {resultado['fi_atualizados']} | "
              f"FII: {resultado['fii_atualizados']} | "
              f"Não encontrados: {len(resultado['nao_encontrados'])} | "
              f"Sem CNPJ: {resultado['sem_cnpj']}")

        return resultado

    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================

    def _calcular_meses(self):
        """
        Retorna tuplas (ano, mes) para mês atual e mês anterior.

        Returns:
            tuple: ((ano_atual, mes_atual), (ano_anterior, mes_anterior))
        """
        hoje = datetime.now()
        primeiro_dia = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia - timedelta(days=1)

        mes_atual    = (hoje.year, hoje.month)
        mes_anterior = (ultimo_dia_mes_anterior.year, ultimo_dia_mes_anterior.month)

        return mes_atual, mes_anterior

    def _buscar_cota(self, cnpj_norm, df_atual, df_anterior):
        """
        Busca o valor de cota mais recente para um CNPJ.
        Prioriza mês atual, faz fallback para mês anterior.

        Args:
            cnpj_norm: CNPJ sem pontuação
            df_atual: DataFrame do mês atual (pode ser vazio)
            df_anterior: DataFrame do mês anterior (pode ser vazio)

        Returns:
            float | None
        """
        for df in [df_atual, df_anterior]:
            if df.empty:
                continue

            registros = df[df['CNPJ_NORM'] == cnpj_norm]

            if not registros.empty:
                mais_recente = registros.sort_values('DT_COMPTC', ascending=False).iloc[0]
                return float(mais_recente['VL_QUOTA'])

        return None

    def _buscar_cota_fii(self, cnpj_norm, df_fii):
        """
        Busca o valor patrimonial da cota mais recente para um FII.

        Args:
            cnpj_norm: CNPJ sem pontuação
            df_fii: DataFrame do informe mensal FII

        Returns:
            float | None
        """
        if df_fii.empty:
            return None

        registros = df_fii[df_fii['CNPJ_NORM'] == cnpj_norm]

        if registros.empty:
            return None

        mais_recente = registros.sort_values('Data_Referencia', ascending=False).iloc[0]
        valor = mais_recente['Valor_Patrimonial_Cotas']

        if pd.isna(valor) or valor <= 0:
            return None

        return float(valor)

    def _atualizar_fundo(self, fundo, nova_cota):
        """Aplica nova cota ao objeto ORM (sem commit)."""
        valor_antigo = float(fundo.valor_cota) if fundo.valor_cota else 0.0
        fundo.valor_cota = nova_cota
        fundo.data_atualizacao = datetime.now()
        print(f"[COTAS] ✅ {fundo.nome_fundo[:40]}: {valor_antigo:.4f} → {nova_cota:.4f}")

    def _normalizar_cnpj(self, cnpj):
        """Remove pontuação do CNPJ."""
        return cnpj.replace('.', '').replace('/', '').replace('-', '')