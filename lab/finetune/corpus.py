"""The sentences you read to build a voice dataset.

Two halves, on purpose:

* **Domínio** -- what the assistant will actually say. A TTS trained mostly on
  what it will speak sounds better at that job than one trained on novels.
* **Fonética** -- sentences chosen to sweep sounds the first half misses:
  nasals, open and closed vowels, consonant clusters, questions, foreign words.

Read them the way you want the assistant to sound. The model copies your pace,
your pauses and your mood, so a bored reading gives a bored voice.
"""

from __future__ import annotations

from lab.finetune.corpus_long import LONGAS

DOMINIO = [
    "Timer de dez minutos.",
    "Timer de cinco minutos, começando agora.",
    "Alarme criado para as sete da manhã.",
    "Alarme criado para as seis e meia.",
    "O alarme foi cancelado.",
    "Cancelei todos os timers.",
    "Faltam três minutos e vinte segundos.",
    "O tempo acabou.",
    "São nove e quarenta e sete da noite.",
    "Agora são quinze para as sete.",
    "Hoje é terça-feira, dezoito de março.",
    "Bom dia! Como você dormiu?",
    "Boa noite, durma bem.",
    "Boa tarde. Em que posso ajudar?",
    "Certo, já anotei.",
    "Pronto, está feito.",
    "Não consegui entender. Pode repetir?",
    "Desculpa, não entendi direito.",
    "Não tenho certeza sobre isso.",
    "Não encontrei nada sobre esse assunto.",
    "Estou sem conexão com a internet agora.",
    "Acendi a luz do quarto.",
    "Apaguei as luzes da sala.",
    "Diminuí o volume para trinta por cento.",
    "Aumentei o volume.",
    "Pausei a música.",
    "Tocando a próxima faixa.",
    "Coloquei a sua playlist favorita para tocar.",
    "A temperatura lá fora está em vinte e três graus.",
    "A previsão é de chuva no fim da tarde.",
    "Amanhã a máxima deve chegar a trinta e um graus.",
    "Você tem um compromisso às quatorze horas.",
    "Seu primeiro lembrete é comprar pão.",
    "Adicionei arroz à lista de compras.",
    "Sua lista tem quatro itens.",
    "Vou te lembrar disso amanhã de manhã.",
    "Isso vai levar mais ou menos vinte minutos.",
    "Só um instante, estou verificando.",
    "Deixa eu pensar um pouco.",
    "Acho que é melhor você conferir isso depois.",
    "Quer que eu repita?",
    "Posso fazer mais alguma coisa?",
    "Até logo!",
    "Estou aqui se precisar.",
    "Entendi. Vou deixar tudo pronto.",
]

FONETICA = [
    "O avô do José põe açúcar no pão às três da manhã.",
    "A manhã de domingo amanheceu limpa e silenciosa.",
    "João comprou pêssego, caqui e maracujá na feira.",
    "Nenhuma criança lembrou de trazer o guarda-chuva.",
    "O caminhão atravessou a ponte antes do amanhecer.",
    "Ele trabalhou o dia inteiro sem reclamar de nada.",
    "A chuva bateu forte na janela durante a madrugada.",
    "Trouxe três pratos, quatro copos e um garfo torto.",
    "O engenheiro explicou o problema com muita paciência.",
    "Quantas vezes você já tentou consertar essa tranca?",
    "Será que ela vai chegar antes das oito e meia?",
    "Por que ninguém avisou que a reunião foi adiada?",
    "Onde foi que você guardou as chaves do carro?",
    "Que horas o filme começa hoje à noite?",
    "Você prefere café com leite ou chá de camomila?",
    "A exposição fica aberta até o fim do próximo mês.",
    "O relógio antigo da estação parou às cinco horas.",
    "Aquele cachorro pequeno late a noite toda sem parar.",
    "Meu irmão mais novo estuda engenharia em Campinas.",
    "A estrada estava cheia de curvas e buracos profundos.",
    "Colhemos flores amarelas no jardim da minha avó.",
    "O vento frio soprava entre as árvores da praça.",
    "Trinta e sete pessoas assinaram o documento ontem.",
    "O preço subiu de dezenove para vinte e quatro reais.",
    "Ela guardou as fotografias numa caixa de madeira.",
    "Ninguém imaginava que aquilo daria tão certo.",
    "O barulho do trem acordou toda a vizinhança.",
    "Aprendi a cozinhar feijão observando meu pai.",
    "As crianças correram até o final da rua sem parar.",
    "Um pássaro azul pousou no galho mais alto.",
    "Precisamos revisar todos os cálculos antes de enviar.",
    "O médico recomendou repouso durante uma semana inteira.",
    "Havia muitos livros empilhados sobre a escrivaninha.",
    "Encontrei o endereço num papel amassado no bolso.",
    "A viagem de ônibus demorou quase nove horas.",
    "Ele assobiava uma música antiga enquanto caminhava.",
    "Guarde o troco, por favor, não precisa devolver.",
    "O bolo de chocolate ficou pronto rápido demais.",
    "Aquela história não faz o menor sentido para mim.",
    "Vamos tentar de novo com um pouco mais de calma.",
    "O gato subiu no telhado e não quis descer.",
    "A luz do corredor piscou algumas vezes e apagou.",
    "Recebemos a notícia com bastante surpresa e alegria.",
    "Sempre que chove, aquela rua fica completamente alagada.",
    "Tocou a playlist Discover Weekly no Spotify da sala.",
    "Fiz o download do arquivo e mandei por e-mail.",
    "O software novo travou logo depois da atualização.",
    "Meu notebook desligou sozinho no meio do trabalho.",
    "Hoje eu não tenho a menor vontade de sair de casa.",
    "Fique tranquilo, ainda dá tempo de resolver tudo.",
]

#: Everything you read, in order.
#:
#: The index of a sentence IS the name of its wav file, so this list may only
#: ever grow at the end. Reordering or inserting silently pairs old recordings
#: with new text, and the model learns to say the wrong words.
SENTENCES: list[str] = DOMINIO + FONETICA + LONGAS
