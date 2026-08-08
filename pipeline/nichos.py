"""
Configurações específicas por nicho.

Cada nicho pode ter:
- Prompt de ideação personalizado
- Prompt de roteirização personalizado
- Fontes de tendências configuradas
- Distribuição de ideias específica
"""
from typing import NamedTuple


class ConfigNicho(NamedTuple):
    """Configuração de um nicho específico."""
    nome: str
    prompt_ideacao: str
    prompt_roteiro_adicional: str
    prompt_roteiro_short: str  # Subfase 8.5 — Prompt para shorts nativos
    categoria_google_trends: int
    subreddits_sugeridos: list[str]


# Configurações de cada nicho
NICHOS_CONFIG: dict[str, ConfigNicho] = {
    "cultura_pop": ConfigNicho(
        nome="cultura_pop",
        prompt_ideacao="""\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de Cultura Pop, Nerd e "Lore" profunda.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações definitivas ou listas
   categorizadas (ex: "Todos os X de Y Explicados", "Os N Elementos mais
   Sombrios de Y").
2. Tom: pode usar adjetivos fortes (Sombrio, Brutal, Trágico, Épico,
   Fascinante), cobrindo terror, mistério, redenção, rivalidades, lore.
3. Foco 100% em Lore — ignore esportes e jogos competitivos sem narrativa.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Anime): obrigatoriamente um anime presente nas tendências.
- Ideia 2 (Filme/Série): obrigatoriamente uma obra presente nas tendências.
- Ideia 3 (Jogo): um jogo das tendências, ou um jogo atemporal de lore
  profunda (Elden Ring, Dark Souls, God of War) se não houver jogo nas
  tendências.
- Ideias 4 e 5 (Evergreen): temas atemporais e gerais de cultura pop/ficção.

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Nome da Obra ou Tema Geral",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / qual Lore será explicada"
    }}
  ]
}}
""",
        prompt_roteiro_adicional="""\
DIRETRIZES ADICIONAIS PARA CULTURA POP:
- Cite nomes reais de personagens, lugares e eventos
- Use terminologia de fandom quando apropriado
- Evite spoilers explícitos de obras recentes (< 6 meses)
- Estilo visual: favoreça ken_burns para cenas atmosféricas. Use vox_motion
  pontualmente para linhas do tempo de eventos de lore ou comparações de
  poderes/personagens.
""",
        prompt_roteiro_short="""\
DIRETRIZES PARA SHORTS DE CULTURA POP:
- Gancho nos primeiros 1-2 segundos: revelação imediata ou pergunta impactante
- Uma única ideia central: foque em UM personagem, evento ou mistério
- Fechamento que induza replay: revelação final ou cliffhanger
- Exemplos de ganchos: "O segredo que ninguém percebeu em..." ou "Por que X é o personagem mais trágico de Y"
- 4-8 cenas no total, duração total 25-58 segundos
""",
        categoria_google_trends=22,  # Entertainment
        subreddits_sugeridos=["r/anime", "r/movies", "r/gaming", "r/television"],
    ),

    "tecnologia": ConfigNicho(
        nome="tecnologia",
        prompt_ideacao="""\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de Tecnologia, Programação e Gadgets.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações técnicas acessíveis ou listas
   de ferramentas/conceitos (ex: "As 7 Linguagens que Dominarão 2026",
   "Por que Rust está Substituindo C++").
2. Tom: informativo, técnico mas acessível, focado em tendências reais.
3. Foco em: IA, programação, gadgets, ferramentas, tendências de mercado.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (IA/Machine Learning): tendência de IA ou ML.
- Ideia 2 (Linguagens/Frameworks): linguagem ou framework em alta.
- Ideia 3 (Gadgets/Hardware): gadget ou hardware relevante.
- Ideia 4 (Ferramentas/DevOps): ferramenta ou prática de desenvolvimento.
- Ideia 5 (Evergreen): tema atemporal de tecnologia.

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Nome da Tecnologia ou Tema",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / o que será explicado"
    }}
  ]
}}
""",
        prompt_roteiro_adicional="""\
DIRETRIZES ADICIONAIS PARA TECNOLOGIA:
- Use termos técnicos corretos (API, framework, runtime, etc.)
- Inclua exemplos de código quando relevante (ex: "código Python para...")
- Cite fontes e empresas reais (OpenAI, Google, Microsoft, etc.)
- Evite jargões excessivamente complexos — seja didático.
- Estilo visual: use ken_burns para demonstrações e conceitos gerais. Use
  vox_motion para comparar métricas de performance, adoção de linguagens,
  timelines de versões ou citações de especialistas.
""",
        prompt_roteiro_short="""\
DIRETRIZES PARA SHORTS DE TECNOLOGIA:
- Gancho nos primeiros 1-2 segundos: estatística surpreendente ou afirmação provocativa
- Uma única ideia central: UM conceito, ferramenta ou tendência
- Fechamento que induza replay: dica prática ou conclusão inesperada
- Exemplos de ganchos: "A ferramenta que vai substituir X em 2026" ou "Por que 90% dos devs usam Y errado"
- 4-8 cenas no total, duração total 25-58 segundos
""",
        categoria_google_trends=5,  # Technology
        subreddits_sugeridos=["r/technology", "r/programming", "r/gadgets", "r/artificial"],
    ),

    "futebol": ConfigNicho(
        nome="futebol",
        prompt_ideacao="""\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de Futebol, Táticas e História do Esporte.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de análises táticas ou histórias épicas
   (ex: "Por que o Liverpool Virou uma Máquina", "Os 5 Maiores Erros da
   Final da Champions").
2. Tom: apaixonado mas analítico, focado em táticas, histórias e polêmicas.
3. Foco em: táticas, história, polêmicas, análises de partidas, biografias.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Atual): time ou jogador em destaque nas tendências.
- Ideia 2 (Tática): análise tática de um time ou estilo de jogo.
- Ideia 3 (História): história clássica do futebol (biografia, rivalidade).
- Ideia 4 (Polêmica): polêmica ou debate atual do futebol.
- Ideia 5 (Evergreen): tema atemporal (maiores craques, melhores times, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Time, Jogador ou Tema",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / o que será analisado"
    }}
  ]
}}
""",
        prompt_roteiro_adicional="""\
DIRETRIZES ADICIONAIS PARA FUTEBOL:
- Cite times e jogadores reais (Brasileiros e Internacionais)
- Use terminologia correta (formação 4-3-3, pressing, contra-ataque, etc.)
- Inclua estatísticas quando relevante (gols, títulos, temporadas)
- Evite polêmicas sensíveis (religião, política) — foque no esporte.
- Estilo visual: use ken_burns para jogadas e momentos icônicos. Use
  vox_motion para comparar estatísticas de jogadores, tabelas de campeonatos,
  timelines de carreiras ou citações de comentaristas.
""",
        prompt_roteiro_short="""\
DIRETRIZES PARA SHORTS DE FUTEBOL:
- Gancho nos primeiros 1-2 segundos: estatística absurda ou pergunta polêmica
- Uma única ideia central: UM jogador, time ou momento histórico
- Fechamento que induza replay: revelação final ou convite ao debate
- Exemplos de ganchos: "O jogador que recusou X milhões para ficar no Y" ou "Por que Z é o maior erro da história do futebol"
- 4-8 cenas no total, duração total 25-58 segundos
""",
        categoria_google_trends=20,  # Sports
        subreddits_sugeridos=["r/soccer", "r/football", "r/Brasileirao"],
    ),

    "financas": ConfigNicho(
        nome="financas",
        prompt_ideacao="""\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de Finanças Pessoais, Economia e Investimentos.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações práticas ou revelações financeiras
   (ex: "7 Gastos que Estão Drenando seu Bolso", "Como os Ricos Pagam Menos
   Impostos que Você").
2. Tom: informativo, prático, sem sensacionalismo, focado em valor real.
3. Foco em: finanças pessoais, economia comportamental, investimentos básicos,
   dicas práticas de economia.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Economia Comportamental): armadilhas mentais sobre dinheiro.
- Ideia 2 (Dicas Práticas): métodos de economia ou organização financeira.
- Ideia 3 (Investimentos): conceitos básicos de investimentos para iniciantes.
- Ideia 4 (Tendência Econômica): análise de notícia econômica atual.
- Ideia 5 (Evergreen): tema atemporal (métodos de economia, erros comuns, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Tema Financeiro ou Econômico",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / o que será explicado"
    }}
  ]
}}
""",
        prompt_roteiro_adicional="""\
DIRETRIZES ADICIONAIS PARA FINANÇAS:
- Use números e estatísticas reais (inflação, taxas, percentuais)
- Cite fontes confiáveis (Banco Central, órgãos oficiais) quando relevante
- Evite recomendações específicas de investimentos — foque em educação
- Seja didático: explique termos técnicos de forma acessível
- Estilo visual: use vox_motion para comparar números, gráficos de evolução
  financeira, tabelas de juros compostos ou citações de especialistas.
  Use ken_burns para conceitos gerais e ilustrações.
""",
        prompt_roteiro_short="""\
DIRETRIZES PARA SHORTS DE FINANÇAS:
- Gancho nos primeiros 1-2 segundos: número impactante ou mito financeiro
- Uma única ideia central: UM conceito, dica ou armadilha financeira
- Fechamento que induza replay: dica prática ou revelação surpreendente
- Exemplos de ganchos: "O hábito que está te custando R$ 500 por mês" ou "Por que 90% das pessoas perdem dinheiro em X"
- 4-8 cenas no total, duração total 25-58 segundos
""",
        categoria_google_trends=7,  # Finance
        subreddits_sugeridos=["r/personalfinance", "r/financialindependence", "r/investing", "r/economy"],
    ),

    "ciencia": ConfigNicho(
        nome="ciencia",
        prompt_ideacao="""\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de Ciência, Curiosidades Científicas e Descobertas.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações acessíveis ou revelações científicas
   (ex: "O Mistério dos Buracos Negros Finalmente Explicado", "7 Fatos Sobre
   o Cérebro que Vão Mudar sua Visão").
2. Tom: curioso, didático, focado em fatos científicos verificáveis.
3. Foco em: astronomia, biologia, física, descobertas recentes, curiosidades.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Descoberta Recente): notícia científica atual das tendências.
- Ideia 2 (Astronomia/Universo): tema de astronomia ou espaço.
- Ideia 3 (Biologia/Corpo Humano): curiosidade sobre corpo humano ou natureza.
- Ideia 4 (Física/Tecnologia): conceito de física ou tecnologia científica.
- Ideia 5 (Evergreen): tema atemporal (fatos científicos, mistérios, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Tema Científico ou Descoberta",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / o que será explicado"
    }}
  ]
}}
""",
        prompt_roteiro_adicional="""\
DIRETRIZES ADICIONAIS PARA CIÊNCIA:
- Cite estudos, cientistas e instituições reais
- Use números e medições precisas quando relevante
- Explique conceitos complexos de forma didática e acessível
- Evite pseudociência — foque em fatos verificáveis
- Estilo visual: use vox_motion para comparar escalas (tamanhos, distâncias),
  timelines de descobertas, gráficos de dados ou citações de cientistas.
  Use ken_burns para conceitos visuais (galáxias, células, fenômenos).
""",
        prompt_roteiro_short="""\
DIRETRIZES PARA SHORTS DE CIÊNCIA:
- Gancho nos primeiros 1-2 segundos: fato surpreendente ou pergunta instigante
- Uma única ideia central: UM fato, conceito ou descoberta científica
- Fechamento que induza replay: revelação final ou pergunta em aberto
- Exemplos de ganchos: "O fato científico que contradiz tudo que você sabia sobre X" ou "Por que a ciência ainda não consegue explicar Y"
- 4-8 cenas no total, duração total 25-58 segundos
""",
        categoria_google_trends=11,  # Science
        subreddits_sugeridos=["r/science", "r/space", "r/askscience", "r/curiosity"],
    ),

    "historia": ConfigNicho(
        nome="historia",
        prompt_ideacao="""\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de História, Geopolítica e Documentários.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de narrativas épicas ou revelações históricas
   (ex: "O Império que Destruiu Roma de Dentro", "A Guerra que Mudou o Mapa
   Mundial Para Sempre").
2. Tom: narrativo, dramático, focado em histórias reais e eventos verificáveis.
3. Foco em: civilizações antigas, guerras históricas, geopolítica, biografias.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Evento Histórico): tema histórico de relevância atual ou aniversário.
- Ideia 2 (Civilização/Império): história de civilização ou império antigo.
- Ideia 3 (Geopolítica): análise geopolítica histórica ou atual.
- Ideia 4 (Biografia): biografia de figura histórica importante.
- Ideia 5 (Evergreen): tema atemporal (grandes batalhas, mistérios, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Tema Histórico ou Geopolítico",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / o que será narrado"
    }}
  ]
}}
""",
        prompt_roteiro_adicional="""\
DIRETRIZES ADICIONAIS PARA HISTÓRIA:
- Cite datas, locais e figuras históricas corretas
- Use mapas e referências geográficas quando relevante
- Mantenha neutralidade em temas geopolíticos sensíveis
- Foque em narrativa e storytelling — torne a história envolvente
- Estilo visual: use vox_motion para timelines de eventos, comparações de
  territórios, árvores genealógicas ou citações históricas. Use ken_burns
  para mapas, pinturas históricas e conceitos visuais.
""",
        prompt_roteiro_short="""\
DIRETRIZES PARA SHORTS DE HISTÓRIA:
- Gancho nos primeiros 1-2 segundos: fato histórico surpreendente ou pergunta
- Uma única ideia central: UM evento, figura ou civilização histórica
- Fechamento que induza replay: revelação final ou conexão com o presente
- Exemplos de ganchos: "O imperador que governou por apenas X dias" ou "Por que o maior império da história ruiu tão rápido"
- 4-8 cenas no total, duração total 25-58 segundos
""",
        categoria_google_trends=24,  # Society
        subreddits_sugeridos=["r/history", "r/AskHistorians", "r/geopolitics", "r/MapPorn"],
    ),
}


def obter_config_nicho(nicho: str) -> ConfigNicho:
    """
    Retorna a configuração de um nicho.

    Args:
        nicho: Nome do nicho (cultura_pop, tecnologia, futebol)

    Returns:
        ConfigNicho configurado

    Raises:
        ValueError: Se o nicho não existir
    """
    if nicho not in NICHOS_CONFIG:
        raise ValueError(
            f"Nicho '{nicho}' não configurado. "
            f"Nichos disponíveis: {list(NICHOS_CONFIG.keys())}"
        )
    return NICHOS_CONFIG[nicho]


def listar_nichos_disponiveis() -> list[str]:
    """Retorna lista de todos os nichos configurados."""
    return list(NICHOS_CONFIG.keys())
