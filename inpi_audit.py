"""
Pharmyrus INPI Audit Module
============================

Compara resultados encontrados vs Cortellis Excel benchmark
Gera métricas de recall, precision e classificação de performance
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import re

logger = logging.getLogger("pharmyrus.audit")


class INPIAuditLayer:
    """
    Auditoria de resultados vs Cortellis benchmark
    """
    
    # Benchmark Cortellis por molécula (extraído dos Excels)
    # TODO: Carregar de arquivo Excel quando disponível
    CORTELLIS_BENCHMARKS = {
        'darolutamide': {
            'expected_brs': [
                'BR112017027822',
                'BR112018076865',
                'BR112019014776',
                'BR112020008364',
                'BR112020023943',
                'BR112021001234',  # Exemplos
                'BR112021005678',
                'BR112022009876',
            ],
            'expected_wos': 174,  # Total WO patents
        },
        'ixazomib': {
            'expected_brs': [],  # TODO: Adicionar do Excel
            'expected_wos': 0,
        },
        'niraparib': {
            'expected_brs': [],
            'expected_wos': 0,
        },
        'olaparib': {
            'expected_brs': [],
            'expected_wos': 0,
        },
        'venetoclax': {
            'expected_brs': [],
            'expected_wos': 0,
        },
        'trastuzumab': {
            'expected_brs': [],
            'expected_wos': 0,
        },
        # Adicionar mais moléculas conforme Excels
    }
    
    def __init__(self, molecule_name: str):
        self.molecule_name = molecule_name.lower()
        self.benchmark = self._get_benchmark()
    
    def _get_benchmark(self) -> Dict[str, Any]:
        """
        Busca benchmark do Cortellis para a molécula
        """
        benchmark = self.CORTELLIS_BENCHMARKS.get(self.molecule_name, {})
        
        if not benchmark or not benchmark.get('expected_brs'):
            logger.warning(f"⚠️  Sem benchmark Cortellis para '{self.molecule_name}'")
            return {
                'expected_brs': [],
                'expected_wos': 0,
                'has_benchmark': False
            }
        
        benchmark['has_benchmark'] = True
        return benchmark
    
    def audit_results(
        self,
        found_brs: List[str],
        found_wos: int,
        strategy_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Audita resultados encontrados vs Cortellis
        
        Args:
            found_brs: Lista de BRs encontradas (números normalizados)
            found_wos: Total de WO patents encontradas
            strategy_details: Detalhes de cada estratégia INPI
        
        Returns:
            Audit report completo com métricas
        """
        logger.info("📊 Gerando relatório de auditoria...")
        
        if not self.benchmark['has_benchmark']:
            return self._create_no_benchmark_report(found_brs, found_wos)
        
        # Normalizar números de patentes
        expected_brs = [self._normalize_patent_number(br) for br in self.benchmark['expected_brs']]
        found_brs_normalized = [self._normalize_patent_number(br) for br in found_brs]
        
        # Classificação
        matched = set(found_brs_normalized) & set(expected_brs)
        missing = set(expected_brs) - set(found_brs_normalized)
        extra = set(found_brs_normalized) - set(expected_brs)
        
        # Métricas
        total_expected = len(expected_brs)
        total_found = len(found_brs_normalized)
        total_matched = len(matched)
        
        recall = (total_matched / total_expected * 100) if total_expected > 0 else 0
        precision = (total_matched / total_found * 100) if total_found > 0 else 0
        f1_score = (2 * recall * precision / (recall + precision)) if (recall + precision) > 0 else 0
        
        # Performance vs Cortellis
        if total_found > total_expected:
            vs_cortellis_percent = ((total_found - total_expected) / total_expected * 100)
            vs_cortellis_status = "BETTER"
        elif total_found == total_expected:
            vs_cortellis_percent = 0
            vs_cortellis_status = "EQUAL"
        else:
            vs_cortellis_percent = -((total_expected - total_found) / total_expected * 100)
            vs_cortellis_status = "WORSE"
        
        # Classificação qualitativa
        quality_rating = self._calculate_quality_rating(recall, precision)
        
        # Análise por estratégia
        strategy_performance = self._analyze_strategy_performance(
            strategy_details,
            matched,
            missing
        )
        
        audit_report = {
            'molecule': self.molecule_name,
            'has_benchmark': True,
            'comparison': {
                'expected_brs': total_expected,
                'found_brs': total_found,
                'matched_brs': total_matched,
                'missing_brs': len(missing),
                'extra_brs': len(extra),
            },
            'metrics': {
                'recall_percent': round(recall, 2),
                'precision_percent': round(precision, 2),
                'f1_score': round(f1_score, 2),
            },
            'vs_cortellis': {
                'status': vs_cortellis_status,
                'difference_percent': round(vs_cortellis_percent, 2),
                'quality_rating': quality_rating,  # BAIXO, MÉDIO, ALTO
            },
            'matched_patents': sorted(list(matched)),
            'missing_patents': sorted(list(missing)),
            'extra_patents': sorted(list(extra)),
            'strategy_performance': strategy_performance,
            'wo_patents': {
                'expected': self.benchmark.get('expected_wos', 0),
                'found': found_wos,
                'difference': found_wos - self.benchmark.get('expected_wos', 0)
            }
        }
        
        logger.info(f"✅ Auditoria completa:")
        logger.info(f"   Recall: {recall:.1f}%")
        logger.info(f"   Precision: {precision:.1f}%")
        logger.info(f"   Rating: {quality_rating}")
        logger.info(f"   vs Cortellis: {vs_cortellis_status} ({vs_cortellis_percent:+.1f}%)")
        
        return audit_report
    
    def _normalize_patent_number(self, patent_number: str) -> str:
        """
        Normaliza número de patente para comparação
        
        Exemplos:
            BR112017027822 → BR112017027822
            BR-112017027822 → BR112017027822
            BR 112017027822 → BR112017027822
        """
        if not patent_number:
            return ""
        
        # Remove espaços, hífens, barras
        normalized = re.sub(r'[\s\-/]', '', patent_number.upper())
        
        # Garante que começa com BR
        if not normalized.startswith('BR'):
            normalized = 'BR' + normalized
        
        return normalized
    
    def _calculate_quality_rating(self, recall: float, precision: float) -> str:
        """
        Calcula rating qualitativo baseado em recall e precision
        
        ALTO: Recall >= 90% AND Precision >= 80%
        MÉDIO: Recall >= 70% OR Precision >= 70%
        BAIXO: Outros casos
        """
        if recall >= 90 and precision >= 80:
            return "ALTO"
        elif recall >= 70 or precision >= 70:
            return "MÉDIO"
        else:
            return "BAIXO"
    
    def _analyze_strategy_performance(
        self,
        strategy_details: Dict[str, Any],
        matched: set,
        missing: set
    ) -> Dict[str, Any]:
        """
        Analisa qual estratégia contribuiu mais para o recall
        """
        performance = {}
        
        for strategy_id, details in strategy_details.items():
            performance[strategy_id] = {
                'name': details.get('name', strategy_id),
                'status': details.get('status', 'unknown'),
                'patents_found': details.get('patents_found', 0),
                'contribution_to_recall': 'N/A'  # Requer tracking detalhado
            }
        
        return performance
    
    def _create_no_benchmark_report(
        self,
        found_brs: List[str],
        found_wos: int
    ) -> Dict[str, Any]:
        """
        Cria relatório quando não há benchmark disponível
        """
        return {
            'molecule': self.molecule_name,
            'has_benchmark': False,
            'warning': 'No Cortellis benchmark available for this molecule',
            'found_brs': len(found_brs),
            'found_wos': found_wos,
            'vs_cortellis': {
                'status': 'NO_BENCHMARK',
                'difference_percent': 0,
                'quality_rating': 'N/A'
            }
        }
    
    @classmethod
    def load_benchmarks_from_excel(cls, excel_path: Path) -> bool:
        """
        Carrega benchmarks de arquivo Excel do Cortellis
        
        TODO: Implementar quando Excel estiver disponível
        
        Formato esperado:
            - Coluna 'molecule': Nome da molécula
            - Coluna 'BR_patents': Lista de BRs (separados por vírgula)
            - Coluna 'WO_count': Total de WO patents
        """
        try:
            import pandas as pd
            
            df = pd.read_excel(excel_path)
            
            for _, row in df.iterrows():
                molecule = str(row['molecule']).lower().strip()
                br_patents = str(row.get('BR_patents', '')).split(',')
                wo_count = int(row.get('WO_count', 0))
                
                cls.CORTELLIS_BENCHMARKS[molecule] = {
                    'expected_brs': [br.strip() for br in br_patents if br.strip()],
                    'expected_wos': wo_count
                }
            
            logger.info(f"✅ Benchmarks carregados de {excel_path}")
            logger.info(f"   Total moléculas: {len(cls.CORTELLIS_BENCHMARKS)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro carregando benchmarks: {e}")
            return False
