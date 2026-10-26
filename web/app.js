const connectionForm = document.querySelector('#connectionForm');
const chatForm = document.querySelector('#chatForm');
const flowIdInput = document.querySelector('#flowId');
const apiKeyInput = document.querySelector('#apiKey');
const messageInput = document.querySelector('#messageInput');
const messages = document.querySelector('#messages');
const sendButton = document.querySelector('#sendButton');
const connectionStatus = document.querySelector('#connectionStatus');
const fullOutputInput = document.querySelector('#fullOutput');

const saved = JSON.parse(localStorage.getItem('relayConnection') || '{}');
flowIdInput.value = saved.flowId || '';
apiKeyInput.value = saved.apiKey || '';
if (saved.flowId) setStatus('connected', 'Connection configured');
fullOutputInput.checked = localStorage.getItem('relayFullOutput') === 'true';

function addResponseMessage(data, fallback) {
  const filtered = data.message || fallback;
  const full = data.fullMessage || filtered;
  const article = addMessage('agent', fullOutputInput.checked ? full : filtered);
  article.dataset.filteredMessage = filtered;
  article.dataset.fullMessage = full;
  return article;
}

function setStatus(state, text) {
  connectionStatus.className = `status ${state}`;
  connectionStatus.lastElementChild.textContent = text;
}

function addMessage(role, text, extraClass = '') {
  const article = document.createElement('article');
  article.className = `message ${role} ${extraClass}`.trim();
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const label = role === 'user' ? 'YOU' : 'AGENT';
  article.innerHTML = `<div class="message-meta"><span>${label}</span><time>${now}</time></div><p></p>`;
  article.querySelector('p').textContent = text;
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function showApproval(data) {
  const request = data.request || {};
  const requestId = request.request_id || request.requestId || request.id
    || request.request?.request_id || request.request?.id
    || request.data?.request_id || request.data?.id;
  const prompt = request.prompt || request.description || 'This tool needs your approval to continue.';
  const article = addMessage('agent', prompt, 'approval');
  const toolName = request.tool_name || request.tool || request.name;
  const toolInput = request.tool_input || request.arguments || request.input || request.parameters;
  if (toolName || toolInput) {
    const context = document.createElement('div');
    context.className = 'approval-context';
    if (toolName) {
      const name = document.createElement('div');
      name.innerHTML = '<span>Tool</span>';
      const value = document.createElement('strong');
      value.textContent = typeof toolName === 'string' ? toolName : JSON.stringify(toolName);
      name.append(value);
      context.append(name);
    }
    if (toolInput) {
      const input = document.createElement('div');
      input.innerHTML = '<span>Requested action</span>';
      const value = document.createElement('pre');
      value.textContent = typeof toolInput === 'string'
        ? toolInput
        : JSON.stringify(toolInput, null, 2);
      input.append(value);
      context.append(input);
    }
    article.append(context);
  }
  const choices = Array.isArray(request.allowed_decisions) && request.allowed_decisions.length
    ? request.allowed_decisions
    : ['approve', 'reject'];
  const actions = document.createElement('div');
  actions.className = 'approval-actions';

  if (!requestId) {
    const warning = document.createElement('div');
    warning.className = 'approval-warning';
    warning.textContent = 'Langflow did not provide a request ID, so this approval cannot be resumed.';
    article.append(warning);
    return;
  }

  choices.forEach((choice) => {
    const rawValue = typeof choice === 'string'
      ? choice
      : choice.action_id || choice.value || choice.id || choice.label;
    const value = rawValue == null ? '' : String(rawValue);
    const label = typeof choice === 'string' ? choice : choice.label || value;
    if (!value) return;
    const decision = typeof choice === 'object' && choice !== null
      ? choice
      : { action_id: value };
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = /approve|allow|accept|yes/i.test(value) ? `Approve ${toolName || 'action'}` : label;
    button.className = /reject|deny|decline/i.test(value) ? 'reject' : '';
    button.addEventListener('click', () => resumeWorkflow(data.jobId, requestId, decision, actions));
    actions.append(button);
  });
  article.append(actions);
  messages.scrollTop = messages.scrollHeight;
  setStatus('', 'Waiting for approval');
}

async function resumeWorkflow(jobId, requestId, decision, actions) {
  const buttons = actions.querySelectorAll('button');
  buttons.forEach((button) => { button.disabled = true; });
  setStatus('connected', 'Resuming workflow');
  const pending = addMessage('agent', 'Resuming', 'typing');
  try {
    const response = await fetch('/api/resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jobId,
        requestId,
        apiKey: apiKeyInput.value.trim(),
        decision,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Resume failed (${response.status})`);
    pending.remove();
    actions.remove();
    if (data.status === 'approval_required') showApproval(data);
    else {
      addResponseMessage(data, 'The workflow completed without a text response.');
      setStatus('connected', 'Agent online');
    }
  } catch (error) {
    pending.remove();
    addMessage('agent', error.message, 'error');
    buttons.forEach((button) => { button.disabled = false; });
    setStatus('error', 'Resume failed');
  }
}

connectionForm.addEventListener('submit', (event) => {
  event.preventDefault();
  localStorage.setItem('relayConnection', JSON.stringify({
    flowId: flowIdInput.value.trim(),
    apiKey: apiKeyInput.value.trim(),
  }));
  setStatus('connected', 'Connection configured');
  messageInput.focus();
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  const flowId = flowIdInput.value.trim();
  if (!flowId) {
    setStatus('error', 'Flow ID required');
    flowIdInput.focus();
    return;
  }

  addMessage('user', message);
  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendButton.disabled = true;
  setStatus('connected', 'Agent is working');
  const pending = addMessage('agent', 'Thinking', 'typing');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flowId, apiKey: apiKeyInput.value.trim(), message }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    pending.remove();
    if (data.status === 'approval_required') showApproval(data);
    else {
      addResponseMessage(data, 'The agent returned an empty response.');
      setStatus('connected', 'Agent online');
    }
  } catch (error) {
    pending.remove();
    addMessage('agent', error.message, 'error');
    setStatus('error', 'Request failed');
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});

messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${messageInput.scrollHeight}px`;
});

messageInput.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') chatForm.requestSubmit();
});

document.querySelector('#clearChat').addEventListener('click', () => {
  messages.innerHTML = '';
  addMessage('agent', 'Thread cleared. What would you like to ask?');
});

fullOutputInput.addEventListener('change', () => {
  localStorage.setItem('relayFullOutput', String(fullOutputInput.checked));
  document.querySelectorAll('.message.agent[data-filtered-message]').forEach((article) => {
    article.querySelector('p').textContent = fullOutputInput.checked
      ? article.dataset.fullMessage
      : article.dataset.filteredMessage;
  });
});
