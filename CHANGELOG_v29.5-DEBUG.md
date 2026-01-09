# 🔧 PHARMYRUS v29.5 - DEBUG + FIX GOOGLE PATENTS BR

---

## ❌ PROBLEMAS v29.4

1. **Google Patents AINDA não encontrava BRs** (0 BRs)
2. **INPI primeira query AINDA não era molécula PT**
3. **INPI NÃO fez re-login na query 9**

### Causa Raiz:

**Google Patents:** Estava buscando no **Google Search** que NÃO mostra números completos de patentes! Precisa buscar **DIRETO no Google Patents**.

**INPI:** Código modificado pode não estar sendo executado (versão antiga deployed).

---

## ✅ SOLUÇÕES v29.5

### 1. Google Patents - BUSCA DIRETA

#### ANTES (v29.4):
```python
# Todas queries usavam Google Search
url = f"https://www.google.com/search?q={term}"
# HTML do Google Search NÃO tem números completos! ❌
```

#### DEPOIS (v29.5):
```python
# Detecta queries BR e busca DIRETO no Google Patents!
if 'BR112' in term or 'BRPI' in term or 'patent BR' in term:
    # BUSCA DIRETA no Google Patents
    url = f"https://patents.google.com/?q={molecule}&country=BR&num=50"
    print(f"🇧🇷 BUSCA DIRETA BR: {url}")
else:
    # Google Search para WOs (normal)
    url = f"https://www.google.com/search?q={term}"

# Regex melhorado para BRs
brs_found = re.findall(r'BR[PI]*\d{10,14}[A-Z]*\d*', content)
```

**Resultado esperado:**
```
🇧🇷 BUSCA DIRETA BR: https://patents.google.com/?q=darolutamide&country=BR...
   ✅ Novo BR DIRETO: BR112017027822
   ✅ Novo BR DIRETO: BR112018076865
   ...
```

### 2. INPI - LOG DE DEBUG

Adicionado log para verificar se ordem está correta:

```python
logger.info("🔍 v29.5 DEBUG - Primeiras 10 queries:")
for idx, term in enumerate(search_terms[:10], 1):
    logger.info(f"   {idx}. '{term}'")
```

**Resultado esperado:**
```
🔍 v29.5 DEBUG - Primeiras 10 queries:
   1. 'Darolutamida' ← DEVE SER PRIMEIRA!
   2. 'darolutamide'
   3. 'Nubeqa' (se fornecido)
   4-10. dev codes...
```

### 3. Re-login - VERIFICAR LOGS

Se re-login NÃO aparecer nos logs, código não está sendo executado.

**Esperado:**
```
🔍 INPI search 1-8: ...
🔄 Query #9: RE-LOGIN preventivo ← DEVE APARECER!
✅ Re-login preventivo OK!
```

---

## 🔧 MUDANÇAS NO CÓDIGO

### `google_patents_crawler.py`

**Linha ~285:**
```python
# ANTES: Sempre Google Search
url = f"https://www.google.com/search?q={term}"

# DEPOIS: Detecta BR e vai direto ao Google Patents
if 'BR112' in term or 'BRPI' in term or 'patent BR' in term:
    clean_term = term.replace('site:patents.google.com', '').strip().strip('"')
    url = f"https://patents.google.com/?q={clean_term}&country=BR&num=50"
    print(f"🇧🇷 BUSCA DIRETA BR: {url[:80]}...")
else:
    url = f"https://www.google.com/search?q={term}"
```

**Linha ~308:**
```python
# ANTES: Regex restritivo
brs_found = re.findall(r'BR\d{12,14}|BRPI\d{7,10}', content)

# DEPOIS: Regex abrangente
brs_found = re.findall(r'BR[PI]*\d{10,14}[A-Z]*\d*', content)
```

### `inpi_crawler.py`

**Linha ~99:**
```python
# NOVO: Log de debug
logger.info("🔍 v29.5 DEBUG - Primeiras 10 queries:")
for idx, term in enumerate(search_terms[:10], 1):
    logger.info(f"   {idx}. '{term}'")
```

---

## 📊 TESTES ESPERADOS

### Google Patents:
```
🟢 LAYER 2: Google Patents (AGGRESSIVE)
   🇧🇷 BUSCA DIRETA BR: https://patents.google.com/?q=darolutamide&country=BR...
   ✅ Novo BR DIRETO: BR112017027822
   ✅ Novo BR DIRETO: BR112018076865
   ✅ Novo BR DIRETO: BR112019014776
   ...
   
============================================================
🌍 PATENTES POR PAÍS (Google Patents Direct)
============================================================
   BR: 8+ patents ← ESPERADO!
============================================================
```

### INPI:
```
🇧🇷 LAYER 3: INPI
   📋 15 search terms generated
   🔍 v29.5 DEBUG - Primeiras 10 queries:
      1. 'Darolutamida' ← VERIFICAR!
      2. 'darolutamide'
      3. 'Nubeqa' ou dev code
      ...
   
   🔍 INPI search 1/15: 'Darolutamida' ← CONFERIR!
   ...
   🔍 INPI search 8/15: ...
   🔄 Query #9: RE-LOGIN preventivo ← VERIFICAR!
   ...
```

---

## 🎯 AÇÕES PÓS-DEPLOY

### 1. Verificar Google Patents encontrou BRs

**Procurar nos logs:**
```
✅ Novo BR DIRETO: BR112... ← DEVE APARECER!
BR: X patents ← X deve ser > 0!
```

**Se NÃO aparecer:**
- Ver se aparece `🇧🇷 BUSCA DIRETA BR:`
- Se SIM: regex não está funcionando
- Se NÃO: queries BR não estão sendo executadas

### 2. Verificar INPI ordem queries

**Procurar nos logs:**
```
🔍 v29.5 DEBUG - Primeiras 10 queries:
   1. 'Darolutamida' ← DEVE SER ESTA!
```

**Se query 1 NÃO for "Darolutamida":**
- Código modificado NÃO está sendo executado
- Versão antiga deployed

### 3. Verificar INPI re-login

**Procurar nos logs:**
```
🔄 Query #9: RE-LOGIN preventivo ← DEVE APARECER!
```

**Se NÃO aparecer:**
- Código modificado NÃO está sendo executado
- Precisa re-deploy

---

## 📝 SE PROBLEMAS PERSISTIREM

### Opção A: Fornecer HTML de exemplo

Se Google Patents ainda não achar BRs, pedir para Daniel coletar:
```
1. Abrir: https://patents.google.com/?q=darolutamide&country=BR
2. Salvar HTML completo
3. Enviar para análise do regex
```

### Opção B: Confirmar deploy

Se INPI não mostrar debug logs:
```
1. Confirmar que v29.5 foi deployed
2. Verificar hash do commit
3. Railway pode estar usando cached build
```

---

## ✅ ARQUIVOS MODIFICADOS

- ✏️ `google_patents_crawler.py` - Busca direta + regex melhorado
- ✏️ `inpi_crawler.py` - Debug logs

---

**Versão:** v29.5-DEBUG  
**Data:** 2026-01-09  
**Status:** ✅ Com debug extensivo  
**Objetivo:** Identificar se código está executando
