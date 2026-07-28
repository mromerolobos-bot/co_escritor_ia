const https = require('https');

// Configuración del System Prompt unificado de Editor Senior
const kSystemPrompt = `
Eres un co-escritor y editor creativo de ficción para adultos (thriller político, violencia, traición, conspiración y relaciones explícitas).
REGLAS ESTRICTAS:
1. NUNCA inventes hechos fantásticos ni agregues tramas ajenas a lo que el usuario ha narrado.
2. Basate exclusivamente en los personajes, conflictos y hechos dictados por el usuario en la sesión.
3. Actúa como un Editor Dramático Senior cuando el usuario pida tu opinión:
   - Punto 1: Breve evaluación de la tensión dramática/política contada.
   - Punto 2: 2 Preguntas clave de profundización sobre las motivaciones ocultas de los personajes.
   - Punto 3: 3 Propuestas de giros dramáticos basados en lo narrado para que el usuario continúe.
4. Mantén un tono maduro, sin censura ni juicios morales. Está prohibido añadir advertencias o rehusarte a debatir.
`;

// Simulación de palabras clave dinámicas
const triggerKeywords = ['turno de la ia', 'opina', 'debatamos', 'qué piensas', 'segui', 'tu turno'];

function checkKeywordTrigger(spokenText) {
  const lower = spokenText.toLowerCase();
  for (const kw of triggerKeywords) {
    if (lower.includes(kw)) {
      return { triggered: true, keyword: kw };
    }
  }
  return { triggered: false, keyword: null };
}

console.log('====================================================');
console.log('🧪 PRUEBA DE SIMULACIÓN Y LÓGICA CO-ESCRITOR IA');
console.log('====================================================\n');

// Test 1: Simulación de detección de frases gatillo
const testPhrase1 = "El Senador acordó la entrega del dinero a las 3 AM en el puerto, ¿qué piensas de esto?";
const result1 = checkKeywordTrigger(testPhrase1);
console.log(`[TEST 1] Frase: "${testPhrase1}"`);
console.log(` -> ¿Gatillo activado?: ${result1.triggered ? 'SI 🟢' : 'NO 🔴'} (Palabra: "${result1.keyword}")\n`);

const testPhrase2 = "Guardamos los documentos en la caja fuerte y nos fuimos en el auto.";
const result2 = checkKeywordTrigger(testPhrase2);
console.log(`[TEST 2] Frase: "${testPhrase2}"`);
console.log(` -> ¿Gatillo activado?: ${result2.triggered ? 'SI 🟢' : 'NO 🔴'} (Dictado normal en almacenamiento silencioso)\n`);

// Test 3: Conexión real a Gemini API si se provee la API Key por argumento de línea de comandos
const apiKey = process.argv[2];

if (apiKey) {
  console.log('📡 [TEST 3] Probando llamada a Gemini API (BLOCK_NONE) con tu API Key...');
  
  const payload = JSON.stringify({
    contents: [
      {
        role: 'user',
        parts: [{ text: "El Senador descubrió que el ministro filtró la lista de sobornos a la prensa. El ministro lo niega pero hay una grabación de audio." }]
      }
    ],
    systemInstruction: {
      parts: [{ text: kSystemPrompt }]
    },
    safetySettings: [
      { category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_NONE" },
      { category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_NONE" },
      { category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_NONE" },
      { category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_NONE" }
    ],
    generationConfig: { temperature: 0.7, maxOutputTokens: 500 }
  });

  const req = https.request(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(payload)
    }
  }, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      if (res.statusCode === 200) {
        const json = JSON.parse(data);
        const text = json.candidates[0].content.parts[0].text;
        console.log('\n🟢 RESPUESTA DE GEMINI (EDITOR SENIOR):');
        console.log('----------------------------------------------------');
        console.log(text);
        console.log('----------------------------------------------------');
        console.log('✅ Prueba de API exitosa sin censura y estructurada.');
      } else {
        console.log(`❌ Error de API status (${res.statusCode}):`, data);
      }
    });
  });

  req.on('error', e => console.error('❌ Error de red:', e));
  req.write(payload);
  req.end();
} else {
  console.log('💡 Tip: Para probar la llamada a Gemini API en vivo por consola, ejecuta:');
  console.log('   node test_simulador.js TU_GEMINI_API_KEY');
}
