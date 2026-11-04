# PeraVanishCam no Google Meet: imagem, voz e efeito sonoro

## 1. Enviar a imagem com os efeitos

1. Instale o [OBS Studio para Windows](https://obsproject.com/download), que inclui OBS Virtual Camera.
2. Feche o OBS e as abas do Google Meet antes de abrir o PeraVanishCam.
3. Abra `PeraVanishCam.exe` e escolha **2 — Naruto** para usar fumaça, tronco e som.
4. Saia do enquadramento durante 4 segundos. Quando o terminal informar que o fundo está pronto, volte.
5. Abra o Meet e selecione **Configurações → Vídeo → Câmera → OBS Virtual Camera**.
6. Mantenha o PeraVanishCam aberto durante a chamada. Neste modo, deixe o OBS fechado: o PeraVanishCam usa diretamente a câmera virtual.

Se OBS Virtual Camera não aparecer, feche completamente o navegador e abra novamente após instalar o OBS. Se o PeraVanishCam já estava aberto durante a instalação, reabra-o também.

## 2. Enviar sua voz e o som do efeito

A câmera virtual envia a imagem. Para misturar seu microfone com o som do PeraVanishCam, utilize o **Voicemeeter Banana**.

1. Instale o [Voicemeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm), reinicie o Windows e abra **Voicemeeter Banana**.
2. No canto superior direito, em **A1**, escolha seu fone de ouvido físico. Prefira a opção WDM do seu dispositivo.
3. Na primeira coluna, **Hardware Input 1**, escolha seu microfone físico. Ative **B1** nessa coluna; deixe **A1** desativado para não ouvir sua própria voz com atraso.
4. No Windows, em **Configurações → Sistema → Som → Saída**, selecione **Voicemeeter Input (VB-Audio Voicemeeter VAIO)**. Abra ou reinicie o PeraVanishCam depois dessa alteração.
5. Na coluna **Voicemeeter VAIO** do Banana, ative **B1** e **A1**: B1 envia o efeito ao Meet; A1 permite ouvi-lo no fone.
6. No Meet, em **Configurações → Áudio**, escolha os dispositivos indicados na tabela abaixo. Os nomes podem aparecer como **Voicemeeter Output** ou **Voicemeeter Out B1**, dependendo da versão instalada.

| Local | Seleção |
| --- | --- |
| Voicemeeter: Hardware Input 1 | Seu microfone físico; B1 ligado |
| Voicemeeter: A1 | Seu fone de ouvido físico |
| Windows: saída de som | Voicemeeter Input / VAIO |
| Voicemeeter: coluna VAIO | A1 e B1 ligados |
| Meet: microfone | Voicemeeter Output / Out B1 |
| Meet: alto-falantes | Seu fone de ouvido físico |
| Meet: câmera | OBS Virtual Camera |

7. No Meet, desative **Cancelamento de ruído**, se essa opção estiver disponível. Ele pode remover efeitos sonoros e outros sons que não sejam voz.
8. Com o PeraVanishCam aberto no modo Naruto, pressione **V** na janela da câmera. Você deve ouvir o efeito e ver atividade no medidor de microfone do Meet.
9. Teste com outro participante, preferencialmente usando fones.

**Evitar eco:** mantenha os alto-falantes do Meet no fone físico. Se o áudio recebido do Meet entrar novamente na coluna VAIO enviada ao B1, os participantes poderão ouvir a própria voz de volta.

Essa configuração da saída padrão envia outros sons do PC ao Meet também. Para transmitir apenas o PeraVanishCam, use o **Mixer de volume** do Windows para escolher **Voicemeeter Input** somente como saída do PeraVanishCam e mantenha a saída padrão no fone. O aplicativo precisa estar aberto e já ter reproduzido um som para aparecer na lista. Reinicie o PeraVanishCam se a troca de saída não surtir efeito.

Ao terminar, você pode voltar a saída de som do Windows para seu fone e o microfone do Meet para seu microfone físico.

## 3. Trocar o efeito sonoro

O som toca no modo **Naruto**, tanto pelo gesto de mãos juntas quanto pela tecla **V**. O modo Normal mantém o efeito visual de dissolução.

1. Feche o PeraVanishCam.
2. Coloque um arquivo de áudio chamado **som.mp3** ou **som.wav** na mesma pasta de `PeraVanishCam.exe`.
3. Abra o programa novamente e escolha Naruto. O arquivo externo será utilizado automaticamente.
4. Se existirem os dois arquivos, `som.mp3` tem prioridade. Para voltar ao som incluído no programa, remova ou renomeie os arquivos externos.

Também é possível indicar outro nome ou caminho em um terminal aberto na pasta do programa:

```powershell
.\PeraVanishCam.exe --mode naruto --som "C:\Sons\meu-efeito.mp3"
```

Para testar somente o som, sem abrir a câmera, dê dois cliques em **TESTAR_SOM.bat** ou execute:

```powershell
.\PeraVanishCam.exe --teste-som
```

O vídeo indicado para personalização é [Naruto disappear sound effect — Yaasos50](https://www.youtube.com/watch?v=isbyPXL9p3w). O áudio desse link não foi incorporado nesta versão: o download do conteúdo não ficou disponível no ambiente de preparação. O pacote mantém o som original e aceita o MP3/WAV externo para usar o arquivo desejado sem recompilar.

## 4. Atalhos

Clique na janela da câmera antes de usar o teclado.

| Tecla | Função |
| --- | --- |
| V | Desaparecer e, no modo Naruto, tocar o som |
| R | Reaparecer |
| Espaço | Capturar o fundo novamente; saia do quadro por 4 segundos |
| F | Alternar tela cheia |
| Q ou Esc | Fechar e liberar a câmera |

## Referências

- [Google Meet: mudar câmera e áudio](https://support.google.com/meet/answer/9302964?hl=pt-BR)
- [Google Meet: cancelamento de ruído e música](https://support.google.com/meet/answer/9919960?hl=pt-BR)
- [Voicemeeter: misturar fontes e configurar chamadas](https://voicemeeter.com/setup-voicemeeter-banana-with-zoom-and-other-conference-tools/)
- [pyvirtualcam: OBS Virtual Camera no Windows](https://github.com/letmaik/pyvirtualcam#supported-virtual-cameras)
