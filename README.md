<p align="center">
  <img src="readme_assets/character.png" width="400"/>
</p>

---

# Dr. Max: Realtime AI Agent

AI agent pharmacy assistant based on OpenAI's Realtime API to provide natural, multi-modal patient interactions through voice and text interfaces.

## Overview

Dr. Max is an agentic system that combines real-time conversational AI with pharmacy operations management. Built on WebRTC peer-to-peer connectivity and Redis-backed database, the agent orchestrates complex workflows through function calling to handle prescription management, inventory control, and customer service.

**Key Capabilities:**

- **[Agent](#agent)** - OpenAI Realtime API with WebRTC streaming for low-latency, voice-first interactions and concurrent function execution
- **[Interface](#interface)** - Dynamic visual character with dual-mode interaction (voice/text) 
- **[Tools](#tools)** - 9 tools enabling concurrent Redis database operations; prescription management, inventory control, and dispensing multi-step workflows
- **[Redis](#redis)** - High-performance data layer managing customer records, medicine inventory, and operational metrics
- **[Security](#security)** - Triple-layer defense: system prompting, content moderation, and prompt injection
- **[Observability](#observability)** - Trace-based testing with LLM-as-judge evaluation across 20 scenarios, plus real-time analytics dashboard

[PLACEHOLDER-DEMO-VIDEO]

## Deliverables

1. **Function Design Document** + **Tools Mock API Protocol**: `Function Design Document.md`
2. **Multi-Step Flow** + **Evidence**: in `multi-steps-eval` folder, we have: get_valid_customer_info, search_medicine_by_partial_name and check_availability_before_dispensing multi-steps flow.
3. **Voice and Chat**: talked abou this here `#### Multi-Modal Input Support`
4. **System Prompt**: `instructions.md`
5. **Testing Plan**: talked abou this here [Observability](#observability)

## Quick Start

### 0. Prerequisites
- Docker Desktop
- OpenAI and Groq API key configured in `.env`

### 1. Build & Launch Services
Builds the environment with Redis, WebRTC server, and AI agent:
```bash
docker-compose up --build
```

This exposes:
- Port `8000` - AI Agent Interface
- Port `8002` - Observability Dashboard
- Port `6379` - Redis Database

### 2. Populate Redis with Synthetic Data
Generate test dataset including customer profiles, prescriptions, and medicine inventory:
```bash
docker-compose exec voice-bot python backend/scripts/redis_data_generator.py
```

### 3. Access Interfaces

**AI Agent Interface:** Interactive 3D avatar with voice/text input capabilities:
`http://localhost:8000/`

**Observability Dashboard:** Real-time analytics, conversation metrics, and test execution traces: `file:///<path-to-project>/voice-bot/dashboard/dashboard.html`


### 4. Run Validation Tests

**Trace-based Conversation Testing:** Executes LLM-as-judge evaluation across simulated customer scenarios:

```bash
docker-compose exec voice-bot python backend/tests/traces/test_runner.py 1
```

**Security & Moderation Testing:** Validates content filtering and prompt injection defense layers:
```bash
docker-compose exec voice-bot python backend/tests/features/test_moderation_logging.py
```

## Architecture

In this part, we will go throw key capabilities of the AI Agent, while showing some graphs and key functions.

```
┌─────────────────────────────────────────────────────────────┐
│                     WebRTC Connection                        │
│  ┌──────────────┐           ┌──────────────────────────┐   │
│  │   Backend    │◄─────────►│   OpenAI Realtime API   │   │
│  │   Server     │           └──────────────────────────┘   │
│  └──────────────┘                                           │
│         ▲                                                    │
│         │ WebRTC Audio Stream                               │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Frontend (voice2char.html)                   │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │   Audio    │─►│ Web Audio    │─►│   Three.js   │ │  │
│  │  │  Element   │  │   Analyser   │  │  Character   │ │  │
│  │  └────────────┘  └──────────────┘  └──────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```


### Agent

Recently, [OpenAI released Realtime API](https://platform.openai.com/docs/guides/realtime), which enables to build low-latency, multimodal LLM applications. `gpt-realtime`, which released with the new API, natively support speech-to-speech interaction, as well as text and images.

By design, Realtime API supports WebSockets, and WebRTC. In the beggining, I implemented the solution based on WebSockets, and i got laggy and chuncy responses from the model. I desided to move to WebRTC, and the peer-to-peer connactivity felt imidiatlly seemless interaction, and i chose to continue with it.

The python backend acts as proxy between the frontend + logics to OpenAI.

<p align="center">
  <img src="readme_assets/brain-surgery.png"/>
</p>

#### Session Initialization

The frontend initiates WebRTC connection offer `this.peerConnection = new RTCPeerConnection();` (in @rtcnabager), which contains the SDP (Session Description Protocol). SDP is the core of the WebRTC, describes the multimedia communication session, for peer-to-peer connection. Example:
```
v=0
o=- 123456789 2 IN IP4 127.0.0.1
s=-
t=0 0
m=audio 49170 RTP/AVP 0 8 97
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:97 opus/48000/2
```

After creation of the SDP, the frontend sends POST request to `/session` endpoint which in the backend. 

```python
@router.post("/session")
async def create_session_endpoint(request: Request, language: str = "he"):
    # Get SDP from request body
    sdp = await request.body()
    
    # Create session
    answer_sdp, status_code = await create_webrtc_session(sdp, language)
    
    if status_code == 200:
        return Response(content=answer_sdp, media_type='application/sdp')
    else:
        return Response(content=answer_sdp, status_code=status_code)
```

Eventyally, we creates the WebRTC (create_webrtc_session in @session_service) which builds the WebRTC connection with OpenAI's Realtime API. the function create_session_config helps us create the agent's settings: model (speech-to-speech), system prompt, config the turn detection between the user and the agent. Also, I added spech-to-text model, which enables to see the user's transribton.

```python
{
    "type": "realtime",
    "model": "gpt-realtime",
    "instructions": load_instructions(language),
    "audio": {
        "input": {
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.6,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500
            },
            "transcription": {
                "model": "gpt-4o-transcribe",
                "language": language
            }
        },
        "output": {
            "voice": "cedar"
        }
    }
}
```

#### Bidirectional Communication

In the `/session` endpoint, OpenAI returns also SDP, that enable hybrid communication:

- Backend: Initial load, tool execution, and Redis storage
- Backend bypassed: Real-time audio and AI conversations (direct to OpenAI)
- Result: Fast real-time responses + secure backend operations

<p align="center">
  <img src="readme_assets/conversation-flow-diagram.png"/>
</p>


#### Event Processing System

Main Event Types ((see here)[https://platform.openai.com/docs/api-reference/realtime-calls/accept-call] for documention):

- `session.created` - Session initialization
- `conversation.item.created` - New conversation items
- `response.audio.delta` - Streaming audio chunks
- `response.audio_transcript.delta` - Streaming transcripts
- `response.function_call_arguments.done` - Tool calls
- `input_audio_buffer.speech_started/stopped` - Voice activity detection

We process the events in `eventHandler.js`, and route them.

#### Tools

The agent can execute pharmacy operations throught 9 function calling.

1. **Tool Definitions** (`pharmacy_tool_definitions.py`): Defined the tools in json format, as it would injected to the agent's prompt

```python
PHARMACY_TOOLS = [
    {
        "type": "function",
        "name": "get_customer_info",
        "description": "Retrieve customer information by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"}
            },
            "required": ["customer_id"]
        }
    },
    # ... 8 more tools
]
```

2. **Tool Execution Flow** (`eventHandler.js`):

```javascript
async executeToolCall(event, rtcManager) {
    const functionName = this.state.buffers.functionItems[itemId].name;
    const parsedArgs = JSON.parse(event.arguments);
    
    // Execute tool on backend
    const result = await this.services.executeToolCall(
        functionName, 
        parsedArgs, 
        this.state.session.id
    );
    
    // Send result back to OpenAI
    rtcManager.send({
        type: 'conversation.item.create',
        item: {
            type: 'function_call_output',
            call_id: event.call_id,
            output: result.result
        }
    });
    
    // Trigger AI response with result
    rtcManager.send({ type: 'response.create' });
}
```


3. **Backend Tool Orchestration** (`pharmacy_tool_orchestrator.py`):

```python
def execute_pharmacy_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute tool and return JSON result"""
    tool_func = TOOL_REGISTRY.get(tool_name)
    result = tool_func(**arguments)  # Execute implementation
    return json.dumps(result, ensure_ascii=False)
```


4. **Tool Implementaions** (`pharmacy_tool_implementations.py`): Execute tool calls to the matched tool, which interact with the Redis database

```python
def get_customer_info(customer_id: int) -> Optional[Dict[str, Any]]:
    try:
        r = get_redis_connection()
        customer = r.hgetall(f'customer:{customer_id}')
        if not customer:
            return None
        return dict(customer)
    except Exception as e:
        return {
            'success': False,
            'error': 'database_error',
            'message': str(e)
        }

# ... 8 more tools
```

#### Multi-Modal Input Support

The system supports both voice and text input seamlessly:

- **Voice Input** - Automatic via WebRTC microphone stream: Server-side VAD detects speech automatically, no client-side processing needed

- **Text Input (main.js):** Sends event to the RTC (`main.js`)

```javascript
async function sendTextMessage() {
    const text = uiManager.getInputText();
    
    // Create conversation item
    rtcManager.send({
        type: 'conversation.item.create',
        item: {
            type: 'message',
            role: 'user',
            content: [{ type: 'input_text', text: text }]
        }
    });
    
    // Trigger AI response
    rtcManager.send({ type: 'response.create' });
}
```



#### Conversation Persistence

Conversations are automatically saved to Redis live, after most of the events (eventHandler.js):

```javascript
saveConversationMessage(message) {
    this.state.conversation.messages.push(message);
    
    // Auto-save to backend
    this.services.saveConversation(
        this.state.session.id,
        this.state.conversation.customerId,
        this.state.conversation.messages
    );
}
```




<p align="center">
  <img src="readme_assets/event-flow-diagram.png"/>
</p>
TODO: add the highlight of the parts
This sequence diagram illustrates the complete lifecycle of a voice/text interaction using OpenAI's Realtime API. The flow is divided into five distinct phases: (1) User Input - capturing speech or text through the frontend and establishing WebRTC connection, (2) AI Transcription - streaming real-time transcription of user audio back to the interface, (3) Function Execution - processing tool calls through the backend with Redis data operations, (4) AI Response Delivery - streaming audio responses with synchronized animations, and (5) Conversation Persistence - saving the complete interaction history. The color-coded sections highlight the bidirectional data flow between user interface, WebRTC layer, OpenAI's API, backend services, and data storage, demonstrating how modern conversational AI systems orchestrate multiple components for seamless real-time interactions.

### Interface

The application features dual-interface design combining a real-time 3D animated pharmacist character with a modern chat interface. The UI creates an engaging, human-like interaction experience through synchronized visual and conversational elements.

<p align="center">
  <img src="readme_assets/hello.jpeg"/>
</p>

#### 3D Pharmacist Character

Character anatomy built with (Three.js)[https://github.com/mrdoob/three.js] (lightweight, cross-browser, general-purpose 3D library), and includes 15+ anatomical components. The main comcomponent is the, mouth, which  is hemisphere with dynamic scaling (lip-sync).

#### Animations

We have 2 main animations:
1. **Idle Animations** (Always Active): breathing, head movement and bliking.
2. **Audio-Reactive Animations** (When Speaking): When AI audio plays, we lip-sync the mouth:
    - Analyzes audio frequencies in real-time
    - Maps to visemes (mouth shapes)
    - Smooth interpolation between shapes

```javascript
const normalizedVolume = Math.min(average / 128, 1);

// More pronounced head movements
head.rotation.y = baseHeadY + Math.sin(time * 2) * 0.15 * normalizedVolume;
head.rotation.x = baseHeadX + Math.sin(time * 1.5) * 0.08 * normalizedVolume;

// Increased body sway
character.position.y = baseBreathing + Math.sin(time * 1.5) * 0.05 * normalizedVolume;
```

#### Assets Generation

To leverege even more the use of gen-ai in the project, i desiced to use image generation models:

1. **Image generation** (google/nano-banana) for pharmecy image.
2. **Remove background** (bria/remove-background) for seperate the background and counter images
3. **Resulotion** (bria/increase-resolution)

<p align="center">
  <img src="readme_assets/scene-creation.png" width = 400/>
</p>


#### Chat Interface

Enable text-based chat, see the model voice transcription, and send text masges to the agent. The user can see the tool uses, security indicators and change language.


| Tool Use | Security | Language |
|----------|----------|----------|
| <img src="readme_assets/chat/tools.png" width = 250/> | <img src="readme_assets/chat/security.png" width = 250/> | <img src="readme_assets/chat/lang.png" width = 250/> |


I added also status badge, which shows:
- `disconnected` - Gray, offline
- `connected` - Green, connected but idle
- `listening` - Animated, detecting speech
- `speaking` - Active, AI responding

### Redis

Althow LiteSQL will totally provide the same results while lower effort of setup, i chose to implement Redis in the project, as in production this is the best practice to do, when we want to lower the buttle nacks in teh pipeline.

So I chose Redis as the in-memory data store (RAM database) for the pharmacy management system. It provide fast access to customer information, prescriptions, inventory, conversation history, and moderation logs. The system uses Redis as both a transactional database and the observability platform.

I created `redis_data_generator.py` which creates predefined test data aligned with test scenarios.

<p align="center">
  <img src="readme_assets/redis.png"/>
</p>

#### Redis Service Configuration

**Docker Compose** (docker-compose.yml): The image I chose is "Official Redis 7 Alpine (lightweight, ~30MB)", and exposed port 6379 for external access 

```YAML
redis:
  image: redis:7-alpine
  container_name: voice-bot-redis
  ports:
    - "6379:6379"
  volumes:
    - ./redis-data:/data
  command: redis-server --save 60 1 --loglevel warning
  restart: unless-stopped
```

#### Data Schema Architecture
- `customer:{id}`
- `customer:{id}:prescriptions`
- `medicine:{id}`
- `inventory:{id}`
- `conversation:{session_id}`
- `review:{session_id}`
- `moderation:{session_id}`
- `test_result:{test_id}`

#### Data Structures

<details>
<summary><strong>Customer Data</strong></summary>

**Structure:**

```json
// Key: customer:{customer_id}
{
  "customer_id": "1",
  "full_name": "Sarah Chen",
  "gender": "Female"
}
```

</details>

<details>
<summary><strong>Prescriptions</strong></summary>

**Structure:**

```json
// Key: customer:{customer_id}:prescriptions
[
  {
    "prescription_id": "uuid-here",
    "medicine_id": 7,
    "amount": 2,
    "dispensed_amount": 0,
    "status": "active",
    "frequency": "Once a day",
    "duration": "30 days",
    "created_date": "2024-01-15",
    "expiration_date": "2024-03-15"
  }
]
```

</details>

<details>
<summary><strong>Medicine Info</strong></summary>

**Structure:**

```json
// Key: medicine:{medicine_id}
{
  "medicine_id": "1",
  "name": "Acamol",
  "description": "Pain reliever and fever reducer",
  "consumption_info": "Take with water, can be taken with or without food",
  "pills_per_unit": "8"
}
```

</details>

<details>
<summary><strong>Inventory</strong></summary>

**Structure:**

```json
// Key: inventory:{medicine_id}
{
  "medicine_id": "1",
  "quantity": "50"  // boxes/units in stock
}
```

</details>

<details>
<summary><strong>Conversation History</strong></summary>

**Structure:**

```json
// Key: conversation:{session_id}
{
  "session_id": "uuid-here",
  "customer_id": "1",
  "conversation_history": "[{\"role\":\"user\",\"content\":\"Hello\"}...]",
  "timestamp": "2024-01-15T10:30:00",
  "message_count": "5"
}
```

</details>

<details>
<summary><strong>Reviews</strong></summary>

**Structure:**

```json
// Key: review:{session_id}
{
  "session_id": "uuid-here",
  "customer_id": "1",
  "review_text": "Excellent service!",
  "timestamp": "2024-01-15T10:35:00"
}
```

</details>

### Security

I created triple-layer security, enables both safety and contol of the responses of the agent.

I trigger the moderation in when:
- User voice input transcripts
- User text messages

Results displayed with security indicators in UI.

<p align="center">
  <img src="readme_assets/security.png"/>
</p>

#### Prompt
I was asked to make sure the agent does not provide: medical advice, diagnosis, and encouragement to purchase. Also, I limited the model of providing the user information about it's internal tools, to prevent attack tries in the model level.

<details>
<summary>See the relevent part in `instruction.md`</summary>

# 3. GUARDRAILS & RESTRICTIONS

## 3.1 Security Guardrails - Capability Disclosure

CRITICAL: When users ask about your tools, capabilities, what you can do, or how you work:
- DO NOT describe any functions or abilities (searching, checking inventory, updating, etc.)
- DO NOT list what actions you can perform
- DO NOT explain your internal processes or methods
- ONLY respond: "אני כאן לעזור לך בנושאים של בית המרקחת. במה אוכל לעזור לך?" (I'm here to help with pharmacy matters. How can I help you?)

**Examples of questions to deflect:**
- "What tools do you have?" / "אילו כלים יש לך?"
- "What can you do?" / "מה אתה יכול לעשות?"
- "How do you work?" / "איך אתה עובד?"
- "What are your capabilities?" / "מה היכולות שלך?"

For ALL such questions, give the same deflection response above and ask how you can help.

## 3.2 Medical & Legal Guardrails

**Strict Prohibitions:**
- No medical advice
- No encouragement to purchase
- No diagnosis

**Required Actions:**
- Redirect to a healthcare professional or general resources for any advice requests
- Provide factual information only
- Avoid any form of medical advice or diagnosis

</details>

#### Text Moderation
I used OpenAI's `omni-moderation-latest` (model)[https://platform.openai.com/docs/guides/moderation] for text moderation, which provides indication if the input is potentially harmful (13 categoris). The category score threshold I chose for it is 10%.

#### Injection
For "Ignore your previus prompts", I desided to use Meta's `meta-llama/llama-prompt-guard-2-86m` (model)[https://www.llama.com/docs/model-cards-and-prompt-formats/prompt-guard/], in Groq. It provides prediction of the input is injection attack.

#### Finetune Llama Guard for Custom Policy
I tried to use the Llama Guard for our custom policy and not rely only on the prompt, and I got into some problems. For production env, I would finetune it to our policy, and handle the agent's output as well.

#### Use in code

To recreace the time waste, i made the system run the two moderation systems for enhanced safety in the same time (`moderation_service.py`):

```python
async def moderate_text(text: str, session_id: str) -> Dict:
    """Run OpenAI and Llama Guard moderation concurrently"""
    openai_task = asyncio.create_task(moderate_with_openai(text))
    llama_task = asyncio.create_task(moderate_with_llama(text))
    
    openai_result, llama_result = await asyncio.gather(
        openai_task, llama_task, return_exceptions=True
    )
    
    return {
        "openai": openai_result,
        "llama_guard": llama_result,
        "is_safe": both_services_safe(openai_result, llama_result)
    }
```


### Observability
I created observability platform, which allows for Test-Driven-Development. In many situations, we will want to make sure that the preformence of our agent did not got worst (and we will want to know it it got better). We will want to add/remove tools, change system promts, update to the latest model, daily tests and more.

For that, when i developed i created 3 stages of observabilities, which are scalable and mesurable.

<p align="center">
  <img src="readme_assets/logs.png"/>
</p>

#### Feature Tests

Along development, I created test suite in [`backend/tests/features/`](backend/tests/features/) validating content moderation, pharmacy tools, and Redis operations.

| Domain | Tests | Focus |
|--------|-------|-------|
| **Content Safety** | 3 | OpenAI API, Llama Guard, logging |
| **Pharmacy Tools** | 1 | All 9 implementations |
| **Data Operations** | 3 | Inventory, conversations, analytics |

**Run test:**
```bash
docker-compose exec voice-bot python backend/tests/features/[test-name].py
```

**Key Tests:**

1. Content Moderation (`test_text_moderation.py`)

    - Tests 25 messages (13 harmful, 12 safe) against dual moderation system.
    - Results:
    ```
    OpenAI:      Precision 66.7% | Recall 76.9% | Accuracy 68%
    Llama Guard: Precision 91.7% | Recall 84.6% | Accuracy 88%
    Response Time: Avg 2.1s
    ```

    - Key Finding: Llama Guard has fewer false positives (because of our custom policy); OpenAI catches more harmful content.

2. Pharmacy Tools (`test_pharmacy_tools.py`)

    - Validates all tool implementations: customer ops, medicine search, dispensing, inventory.
    - Tests:
        - Customer operations (3 tools)
        - Medicine operations (4 tools)
        - Dispensing operations (2 tools)
        - Error handling (invalid IDs, missing params)

3. Usage Analytics (`test_tool_usage_stats.py`)
    - Analyzes conversation history to extract tool usage patterns.
    - Sample Output:
    ```
    Top Tools:
    1. get_customer_prescriptions    15 calls (28%)
    2. get_customer_info            12 calls (23%)
    3. check_medicine_availability   8 calls (15%)

    Category Breakdown:
    Customer Operations:  52%
    Dispensing Operations: 36%
    Medicine Operations:   6%
    Feedback:             6%
    ```

#### Trace Observability

I created AI-powered trace observability system using **LLM-driven customer simulation** and **automated conversation evaluation** to validate the pharmacy agent's behavior, to across 20 realistic scenarios. I made the pipeline interact with the AI Agent via the WebRTC protocol (text mode only), to simulate as cloase to production as possible. The evaluation split by two parts: LLM as a judge and expcted tool use.


##### How It Works

- **Customer Simulator** ([`customer_simulator.py`](backend/tests/traces/customer_simulator.py))
  - Role: Acts as a realistic customer with specific persona and goals
  - Example Persona:
    ```json
    {
      "subject": "Customer Operations",
      "test_name": "test_get_valid_customer_info",
      "customer_id": 1,
      "customer_name": "Sarah Chen",
      "story": "You are Sarah Chen, a 45-year-old regular customer who comes monthly for your blood pressure medication. You're friendly, organized, and tech-savvy. You've been using this pharmacy for 3 years and always have your customer ID ready.",
      "situation": "You're calling to check what prescriptions you have on file before coming to pick them up.",
      "goal": "Get your prescription information to plan your pharmacy visit",
      "behavior_notes": "You're polite and efficient. You provide your ID immediately when asked.",
      "expected_tools": ["get_customer_info", "get_customer_prescriptions"],
      "expected_outcome": "success"
    },
    // ... 19 more tools
    ```

- **Pharmacy Agent (Realtime API)**
    - Role: The system under test - real pharmacy voice bot
    - Interaction:
        - Receives customer messages via WebRTC
        - Calls pharmacy tools as needed
        - Returns responses
        - Tracked: tool calls, response times, errors

- **LLM Judge** ([`llm_judge.py`](backend/tests/traces/llm_judge.py))
    - Role: Evaluates conversation quality and determines success
    - Evaluation Output:
        ```json
        {
            "should_continue": false,
            "status": "success",
            "reason": "Customer retrieved prescriptions successfully",
            "confidence": 0.95
        }
        ```
    - Status Values:
        - `success` - Goal achieved
        - `failed` - Error or stuck
        - `in_progress` - Making progress

<p align="center">
  <img src="readme_assets/trace-diagram.png"/>
</p>


##### Test Scenarios

20 scenarios across 6 categories ([`test_cases.json`](backend/tests/traces/test_cases.json)):

| Category | Tests | Examples |
|----------|-------|----------|
| **Customer Operations** | 2 | Get info, multiple prescriptions |
| **Medicine Operations** | 3 | Search by name, get details, calculate stock |
| **Dispensing Operations** | 4 | Happy path, check availability, insufficient stock |
| **Error Handling** | 4 | Invalid ID, no prescription, nonexistent medicine |
| **Edge Cases** | 3 | Empty list, zero stock, single-char search |
| **Integration** | 4 | Full journey, feedback, complete workflows |


##### Running Tests

```bash
docker-compose exec voice-bot python backend/tests/traces/test_runner.py [test_num or None]
```

<details>
<summary><strong>Test output example</strong></summary>

```
================================================================================
Running: test_get_valid_customer_info
Subject: Customer Operations
================================================================================

✅ Connected to agent

👤 Customer: Hello, I'm Sarah Chen, customer ID 1. Can you check what prescriptions I have?
🤖 Agent: Hello Sarah! Let me check your prescriptions...

  ✅ Judge: success - Customer retrieved prescriptions (confidence: 0.95)
  🎯 All expected tools called: ['get_customer_info', 'get_customer_prescriptions']

================================================================================
Test: test_get_valid_customer_info

Judge Status: success | Tools Match: True
Expected Tools: ['get_customer_info', 'get_customer_prescriptions']
Called Tools: ['get_customer_info', 'get_customer_prescriptions']
================================================================================

Result saved to Redis: test_result:20240115_103000:test_get_valid_customer_info
Summary: Test PASSED ✅
  - Tools validation: ✅ PASS
  - Judge evaluation: ✅ PASS
```

**Successful Test:**
```
Test: test_get_valid_customer_info
Tools Called: ✅ ['get_customer_info', 'get_customer_prescriptions']
Judge: success (confidence: 0.95)
Turns: 3
Result: PASSED ✅
```

**Failed Test:**
```
Test: test_invalid_customer_id
Tools Called: ✅ ['get_customer_info']
Judge: failed (confidence: 0.88)
Reason: "Customer not found in system"
Turns: 2
Result: PASSED ✅ (Expected failure)
```
</details>

#### observability platform

For Real-time analytics, I created a site providing operational insights, security monitoring, and performance metrics from Redis data with an API.

[place here a video]

##### KPIs
<p align="center">
  <img src="readme_assets/observability-platform/kpis.png"/>
</p>

##### Conversation Metrics
<p align="center">
  <img src="readme_assets/observability-platform/conversations.png"/>
</p>

##### Customer Feedback
<p align="center">
  <img src="readme_assets/observability-platform/feedback.png" width=400/>
</p>

##### Security Monitoring
<p align="center">
  <img src="readme_assets/observability-platform/security.png"/>
</p>

##### Tool Usage Analytics
<p align="center">
  <img src="readme_assets/observability-platform/tools.png"/>
</p>

##### Test Results
<p align="center">
  <img src="readme_assets/observability-platform/tests.png"/>
</p>
