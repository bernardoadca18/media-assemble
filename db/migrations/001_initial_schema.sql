-- ---------------------------------------------------------------------------
-- Migration 001: Initial Schema
-- ---------------------------------------------------------------------------
-- Creates the base schema and tables for Faceless Pipeline
-- ---------------------------------------------------------------------------

-- Create schema
CREATE SCHEMA IF NOT EXISTS dados;

-- ---------------------------------------------------------------------------
-- Table: nichos
-- ---------------------------------------------------------------------------
CREATE TABLE dados.nichos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    prompt_ideacao TEXT NOT NULL,
    prompt_roteiro_adicional TEXT NOT NULL,
    prompt_roteiro_short TEXT NOT NULL,
    categoria_google_trends INTEGER NOT NULL,
    subreddits_sugeridos TEXT[] NOT NULL DEFAULT '{}',
    gameplay_intensidade_preferida VARCHAR(20) NOT NULL DEFAULT 'moderado',
    pitch_shift_semitons FLOAT,
    velocidade_fala FLOAT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX idx_nichos_nome ON dados.nichos(nome);
CREATE INDEX idx_nichos_ativo ON dados.nichos(ativo);

-- ---------------------------------------------------------------------------
-- Seed initial nichos data (from hardcoded config)
-- ---------------------------------------------------------------------------

INSERT INTO dados.nichos (nome, prompt_ideacao, prompt_roteiro_adicional, prompt_roteiro_short, categoria_google_trends, subreddits_sugeridos, gameplay_intensidade_preferida, pitch_shift_semitons, velocidade_fala) VALUES
(
    'cultura_pop',
    'Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube, especialista em canais "Faceless" de Cultura Pop, Nerd e "Lore" profunda.

DADOS DE ENTRADA:
- Tendências Alta nesta semana: {tendencias}
- Histórico vídeos JÁ PUBLICADOS (NÃO repita estes temas): {historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de revelações ou explicações profundas de lore (ex: "O Segredo que Ninguém Percebeu em...", "Por que X é o Personagem Mais Trágico de Y").
2. Tom: nerd, apaixonado, focado em detalhes ocultos e curiosidades de fandom.
3. Foco em: anime, filmes, séries, games, cultura pop em geral.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Tendência): tema em alta nas tendências da semana.
- Ideia 2 (Lore Profunda): explicação de lore complexa de uma obra popular.
- Ideia 3 (Curiosidade): curiosidade ou segredo sobre personagem/obra.
- Ideia 4 (Comparação): comparação de poderes, personagens ou obras.
- Ideia 5 (Evergreen): tema atemporal de cultura pop.

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{
  "ideias": {
    "topico": "Nome da Obra ou Tema Geral",
    "titulo_sugerido": "Título viral seguindo estrutura exigida",
    "descricao_breve": "Resumo do ângulo específico / qual Lore será explicada"
  }
}',
    'DIRETRIZES ADICIONAIS PARA CULTURA POP:
- Cite nomes reais de personagens, lugares e eventos
- Use terminologia de fandom quando apropriado
- Evite spoilers explícitos de obras recentes (< 6 meses)
- Estilo visual: favoreça ken_burns para cenas atmosféricas. Use vox_motion pontualmente para linhas do tempo de eventos de lore ou comparações de poderes/personagens.',
    'DIRETRIZES PARA SHORTS DE CULTURA POP:
- Gancho nos primeiros 1-2 segundos: revelação imediata ou pergunta impactante
- Uma única ideia central: foque em UM personagem, evento ou mistério
- Fechamento que induza replay: revelação final ou cliffhanger
- Exemplos de ganchos: "O segredo que ninguém percebeu em..." ou "Por que X é o personagem mais trágico de Y"
- 4-8 cenas no total, duração total 25-58 segundos',
    22,
    ARRAY['r/anime', 'r/movies', 'r/gaming', 'r/television'],
    'moderado',
    NULL,
    NULL
),
(
    'tecnologia',
    'Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube, especialista em canais "Faceless" de Tecnologia, Programação e Inovação.

DADOS DE ENTRADA:
- Tendências Alta nesta semana: {tendencias}
- Histórico vídeos JÁ PUBLICADOS (NÃO repita estes temas): {historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações técnicas acessíveis ou revelações de tecnologia (ex: "A Nova IA que Vai Substituir Programadores", "Por que 90% dos Devs Usam Esta Ferramenta Errado").
2. Tom: técnico, mas acessível, didático, focado em valor prático.
3. Foco em: IA, programação, ferramentas de desenvolvimento, tendências tech.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Tendência): tecnologia em alta nas tendências da semana.
- Ideia 2 (Ferramenta): análise de ferramenta ou tecnologia popular.
- Ideia 3 (Tutorial): tutorial ou guia prático de tecnologia.
- Ideia 4 (Comparação): comparação de ferramentas ou tecnologias.
- Ideia 5 (Evergreen): tema atemporal de tecnologia.

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{
  "ideias": {
    "topico": "Nome da Tecnologia ou Tema",
    "titulo_sugerido": "Título viral seguindo estrutura exigida",
    "descricao_breve": "Resumo do ângulo específico / o que será explicado"
  }
}',
    'DIRETRIZES ADICIONAIS PARA TECNOLOGIA:
- Use termos técnicos corretos (API, framework, runtime, etc.)
- Inclua exemplos de código quando relevante (ex: "código Python para...")
- Cite fontes e empresas reais (OpenAI, Google, Microsoft, etc.)
- Evite jargões excessivamente complexos — seja didático.
- Estilo visual: use ken_burns para demonstrações e conceitos gerais. Use vox_motion para comparar métricas de performance, adoção de linguagens, timelines de versões ou citações de especialistas.',
    'DIRETRIZES PARA SHORTS TECNOLOGIA:
- Gancho nos primeiros 1-2 segundos: estatística surpreendente ou afirmação provocativa
- Uma única ideia central: UM conceito, ferramenta ou tendência
- Fechamento que induza replay: dica prática ou conclusão inesperada
- Exemplos de ganchos: "A ferramenta que vai substituir X em 2026" ou "Por que 90% dos devs usam Y errado"
- 4-8 cenas no total, duração total 25-58 segundos',
    7,
    ARRAY['r/programming', 'r/technology', 'r/artificial', 'r/webdev'],
    'moderado',
    NULL,
    NULL
),
(
    'futebol',
    'Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube, especialista em canais "Faceless" de Futebol, Análises Táticas e História do Futebol.

DADOS DE ENTRADA:
- Tendências Alta nesta semana: {tendencias}
- Histórico vídeos JÁ PUBLICADOS (NÃO repita estes temas): {historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de análises ou revelações futebolísticas (ex: "O Segredo Tático que Fez Este Time Invencível", "Por que X é o Maior Jogador da História").
2. Tom: apaixonado, analítico, focado em estatísticas e fatos reais.
3. Foco em: times, jogadores, táticas, história do futebol.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Tendência): tema em alta nas tendências da semana.
- Ideia 2 (Tática): análise tática de um time ou estilo de jogo.
- Ideia 3 (História): história clássica do futebol (biografia, rivalidade).
- Ideia 4 (Polêmica): polêmica ou debate atual do futebol.
- Ideia 5 (Evergreen): tema atemporal (maiores craques, melhores times, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{
  "ideias": {
    "topico": "Time, Jogador ou Tema",
    "titulo_sugerido": "Título viral seguindo estrutura exigida",
    "descricao_breve": "Resumo do ângulo específico / o que será analisado"
  }
}',
    'DIRETRIZES ADICIONAIS PARA FUTEBOL:
- Cite times e jogadores reais (Brasileiros e Internacionais)
- Use terminologia correta (formação 4-3-3, pressing, contra-ataque, etc.)
- Inclua estatísticas quando relevante (gols, títulos, temporadas)
- Evite polêmicas sensíveis (religião, política) — foque no esporte.
- Estilo visual: use ken_burns para jogadas e momentos icônicos. Use vox_motion para comparar estatísticas de jogadores, tabelas de campeonatos, timelines de carreiras ou citações de comentaristas.',
    'DIRETRIZES PARA SHORTS DE FUTEBOL:
- Gancho nos primeiros 1-2 segundos: estatística surpreendente ou pergunta impactante
- Uma única ideia central: UM jogador, time ou momento histórico
- Fechamento que induza replay: revelação ou estatística final
- Exemplos de ganchos: "O jogador que passou por 11 clubes em 5 anos" ou "Por que este time é o maior da história"
- 4-8 cenas no total, duração total 25-58 segundos',
    20,
    ARRAY['r/soccer', 'r/football', 'r/soccerbetting', 'r/FIFA'],
    'intenso',
    NULL,
    NULL
),
(
    'financas',
    'Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube, especialista em canais "Faceless" de Finanças, Economia e Investimentos.

DADOS DE ENTRADA:
- Tendências Alta nesta semana: {tendencias}
- Histórico vídeos JÁ PUBLICADOS (NÃO repita estes temas): {historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de dicas práticas ou revelações financeiras (ex: "7 Armadilhas Financeiras que Destroem seu Bolso", "Como os Ricos Pagam Menos Impostos que Você").
2. Tom: informativo, prático, sem sensacionalismo, focado em valor real.
3. Foco em: finanças pessoais, economia comportamental, investimentos básicos, dicas práticas de economia.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Economia Comportamental): armadilhas mentais sobre dinheiro.
- Ideia 2 (Dicas Práticas): métodos de economia ou organização financeira.
- Ideia 3 (Investimentos): conceitos básicos de investimentos para iniciantes.
- Ideia 4 (Tendência Econômica): análise de notícia econômica atual.
- Ideia 5 (Evergreen): tema atemporal (métodos de economia, erros comuns, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{
  "ideias": {
    "topico": "Tema Financeiro ou Econômico",
    "titulo_sugerido": "Título viral seguindo estrutura exigida",
    "descricao_breve": "Resumo do ângulo específico / o que será explicado"
  }
}',
    'DIRETRIZES ADICIONAIS PARA FINANÇAS:
- Use números e estatísticas reais (inflação, taxas, percentuais)
- Cite fontes confiáveis (Banco Central, órgãos oficiais) quando relevante
- Evite recomendações específicas investimentos — foque em educação
- Seja didático: explique termos técnicos
- Estilo visual: use ken_burns para conceitos e demonstrações. Use vox_motion para comparar números, gráficos de inflação, tabelas de rentabilidade ou citações de especialistas.',
    'DIRETRIZES PARA SHORTS FINANCEIROS:
- Gancho nos primeiros 1-2 segundos: número surpreendente ou afirmação provocativa
- Uma única ideia central: UM conceito, dica ou armadilha financeira
- Fechamento que induza replay: dica prática ou revelação final
- Exemplos de ganchos: "O hábito que custa R$ 500 por mês" ou "Por que 80% das pessoas perdem dinheiro investindo"
- 4-8 cenas no total, duração total 25-58 segundos',
    9,
    ARRAY['r/personalfinance', 'r/investing', 'r/economy', 'r/financialindependence'],
    'calmo',
    NULL,
    NULL
),
(
    'ciencia',
    'Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube, especialista em canais "Faceless" de Ciência, Descobertas e Curiosidades Científicas.

DADOS DE ENTRADA:
- Tendências Alta nesta semana: {tendencias}
- Histórico vídeos JÁ PUBLICADOS (NÃO repita estes temas): {historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações acessíveis ou revelações científicas (ex: "O Mistério dos Buracos Negros Finalmente Explicado", "7 Fatos Sobre o Cérebro que Vão Mudar sua Visão").
2. Tom: curioso, didático, focado em fatos científicos verificáveis.
3. Foco em: astronomia, biologia, física, descobertas recentes, curiosidades.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Descoberta Recente): notícia científica atual das tendências.
- Ideia 2 (Astronomia/Universo): tema de astronomia ou espaço.
- Ideia 3 (Biologia/Corpo Humano): curiosidade sobre corpo humano ou natureza.
- Ideia 4 (Física/Tecnologia): conceito de física ou tecnologia científica.
- Ideia 5 (Evergreen): tema atemporal (fatos científicos, mistérios, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{
  "ideias": {
    "topico": "Tema Científico ou Descoberta",
    "titulo_sugerido": "Título viral seguindo estrutura exigida",
    "descricao_breve": "Resumo do ângulo específico / o que será explicado"
  }
}',
    'DIRETRIZES ADICIONAIS PARA CIÊNCIA:
- Cite fontes científicas confiáveis (NASA, Nature, Science, etc.)
- Use números e estatísticas precisas
- Explique conceitos complexos de forma acessível
- Evite sensacionalismo — foque em fatos verificáveis
- Estilo visual: use ken_burns para conceitos e demonstrações. Use vox_motion para comparar escalas, distâncias, timelines de descobertas ou citações de cientistas.',
    'DIRETRIZES PARA SHORTS CIENTÍFICOS:
- Gancho nos primeiros 1-2 segundos: fato surpreendente ou pergunta curiosa
- Uma única ideia central: UM conceito, descoberta ou curiosidade
- Fechamento que induza replay: revelação ou fato final impactante
- Exemplos de ganchos: "O fato científico que contradiz tudo que você sabia" ou "Por que este órgão é o mais importante do corpo"
- 4-8 cenas no total, duração total 25-58 segundos',
    15,
    ARRAY['r/science', 'r/space', 'r/askscience', 'r/EverythingScience'],
    'calmo',
    NULL,
    NULL
),
(
    'historia',
    'Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube, especialista em canais "Faceless" de História, Geopolítica e Documentários.

DADOS DE ENTRADA:
- Tendências Alta nesta semana: {tendencias}
- Histórico vídeos JÁ PUBLICADOS (NÃO repita estes temas): {historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de narrativas épicas ou revelações históricas (ex: "O Império que Destruiu Roma de Dentro", "A Guerra que Mudou o Mapa Mundial Para Sempre").
2. Tom: narrativo, dramático, focado em histórias reais e eventos verificáveis.
3. Foco em: civilizações antigas, guerras históricas, geopolítica, biografias.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Evento Histórico): tema histórico de relevância atual ou aniversário.
- Ideia 2 (Civilização/Império): história de civilização ou império antigo.
- Ideia 3 (Geopolítica): análise geopolítica histórica ou atual.
- Ideia 4 (Biografia): biografia de figura histórica importante.
- Ideia 5 (Evergreen): tema atemporal (grandes batalhas, mistérios, etc.).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{
  "ideias": {
    "topico": "Tema Histórico ou Geopolítico",
    "titulo_sugerido": "Título viral seguindo estrutura exigida",
    "descricao_breve": "Resumo do ângulo específico / o que será explicado"
  }
}',
    'DIRETRIZES ADICIONAIS PARA HISTÓRIA:
- Cite datas, nomes e locais históricos corretos
- Use mapas e referências geográficas quando relevante
- Evite anacronismos — verifique contexto histórico
- Seja respeitoso com eventos sensíveis (guerras, tragédias)
- Estilo visual: use ken_burns para narrativas e mapas. Use vox_motion para timelines de eventos, comparações de impérios, mapas animados ou citações de historiadores.',
    'DIRETRIZES PARA SHORTS HISTÓRICOS:
- Gancho nos primeiros 1-2 segundos: fato surpreendente ou pergunta impactante
- Uma única ideia central: UM evento, pessoa ou civilização
- Fechamento que induza replay: revelação ou desfecho dramático
- Exemplos de ganchos: "O império que durou 500 anos e caiu em 1 dia" ou "Por que este homem mudou a história do mundo"
- 4-8 cenas no total, duração total 25-58 segundos',
    24,
    ARRAY['r/history', 'r/AskHistorians', 'r/geopolitics', 'r/MapPorn'],
    'moderado',
    NULL,
    NULL
);

-- ---------------------------------------------------------------------------
-- Trigger for updating atualizado_em timestamp
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_nichos_updated_at
    BEFORE UPDATE ON dados.nichos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
