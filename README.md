# Helpline Project Plan

## Overview
A web/CLI app that connects users directly to live customer support agents. The system allows users to provide a help line number and a brief description of their issue. An automated agent then uses Twilio to call the support number and OpenAI API (LLM) to navigate phone prompts. When the support person is on the line, the user is alerted to join the call.

## Architecture Breakdown

### 1. User Interface
- **Web App / CLI Interface**
  - Collects user input: help line number and help prompt.
  - Could start as a CLI tool, later evolved into a web application.
  - Technologies: HTML/CSS/JS (for web), Node.js (for CLI).

### 2. Call Management
- **Twilio Integration**
  - Initiates outbound calls to the support line.
  - Handles call status and events.
  - Uses Twilio Voice SDK or API.

### 3. Automated Agent
- **LLM Integration**
  - Uses OpenAI API to parse the user prompt and generate responses for navigating automated phone menus.
  - Learns and adapts answers based on phone prompts provided by the support system.

### 4. Call Bridging
- **Alerting the User**
  - Monitors for when a live support agent is present on the call.
  - Notifies the user to join the call.

### 5. Testing & Deployment
- **Testing**
  - Use a personal number and stage environment to simulate real calls.
  - Unit and integration tests for both API interactions and CLI/web functionalities.
- **Deployment**
  - Start with a simple MVP and gradually enhance features.
  - Prioritize core functionalities before refining the web interface.

## Development Roadmap
1. **Phase 1: MVP**
   - **Subphase 1.1: Text-Based Navigation**
     - Hand-feed the agent pre-converted text from a simulated customer support line.
     - Focus on developing the logic for the agent to navigate phone menus using text input.
     - Test the agent's ability to interpret prompts and generate appropriate responses.
- **Subphase 1.2: Audio-to-Text Integration**
     - Add audio-to-text conversion using OpenAI's Whisper API for transcription.
     - Simulate phone prompts with pre-recorded audio and test the agent's ability to handle real-time transcription.
     - Compare Whisper's performance with other APIs (e.g., Google Speech-to-Text or Twilio) to ensure the best fit for your use case.
   - **Subphase 1.3: Twilio Call Integration**
     - Implement Twilio's call initiation and handling features.
     - Integrate the audio-to-text pipeline with live calls.
     - Test the agent's ability to navigate real phone systems and handle edge cases (e.g., unexpected prompts).

2. **Phase 2: Core Functionality**
   - Enhance the automated agent’s ability to navigate phone prompts.
   - Implement alerting mechanism for user when a support agent is reached.

3. **Phase 3: Web Interface**
   - Build a minimal web application to replace the CLI.
   - Improve usability and add additional monitoring/dashboard features.

4. **Phase 4: Testing and Refinement**
   - API and integration tests for both Twilio and OpenAI components.
   - User testing to adjust LLM responses and improve call handling.

## Further Considerations
- **Scalability**
  - Design to scale from single call handling to multiple concurrent connections.
- **Security**
  - Secure API keys and user data.
- **Extensibility**
  - Modular design to allow easy integration of additional features or service providers.
