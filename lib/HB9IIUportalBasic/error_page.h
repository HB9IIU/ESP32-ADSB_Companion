#pragma once
const char html_error[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>WiFi Error</title>
    <style>
      body {
        font-family: sans-serif;
        text-align: center;
        padding: 2rem;
      }

      a.button {
        display: inline-block;
        margin-top: 20px;
        padding: 10px 20px;
        background: #1b3144;
        color: #fff;
        text-decoration: none;
        border-radius: 4px;
      }

      /* 🔴 blinking red text */
      @keyframes blink {
        0%, 49%   { opacity: 1; }
        50%, 100% { opacity: 0; }
      }

      .blink-red {
        color: #fd0101;
        animation: blink 1s linear infinite;
      }
    </style>
  </head>
  <body>
    <h2 class="blink-red">WiFi connection failed</h2>
    <p>The password seems to be wrong, or the network is not reachable.</p>
    <p>Please go back and try again.</p>
    <p><a class="button" href="/">Back to setup</a></p>
  </body>
</html>


)rawliteral";
