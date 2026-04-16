import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Database,
  Lightbulb,
  Layers,
  Loader2,
  Terminal,
  Trash2,
  X,
} from 'lucide-react';

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const TOOL_EVENT_DELAY_MS = 140;
const RESPONSE_STREAM_DELAY_MS = 16;
const AUTO_SUGGEST_STORAGE_KEY = 'urbantrace-copilot-auto-suggest-enabled';

const FloatingCopilotInput = ({
  nodes = [],
  edges = [],
  suggestions = [],
  autoSuggestRequest,
  onCopilotSuggestions,
  onAcceptSuggestion,
  onRejectSuggestion,
}) => {
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [autoSuggestEnabled, setAutoSuggestEnabled] = useState(() => {
    if (typeof window === 'undefined') return true;
    const storedValue = window.localStorage.getItem(AUTO_SUGGEST_STORAGE_KEY);
    return storedValue === null ? true : storedValue === 'true';
  });
  const [traceLogs, setTraceLogs] = useState([]);
  const [traceMinimized, setTraceMinimized] = useState(true);
  const [suggestionsMinimized, setSuggestionsMinimized] = useState(false);
  const [resolvingSuggestionId, setResolvingSuggestionId] = useState('');
  const [pendingAutoRequests, setPendingAutoRequests] = useState([]);
  const traceBodyRef = useRef(null);
  const previousSuggestionCountRef = useRef(suggestions.length);
  const lastQueuedAutoRequestIdRef = useRef('');
  const autoQueueProcessingRef = useRef(false);

  const traceColorMap = useMemo(() => ({
    user: '#0f172a',
    tool_call: '#0f766e',
    tool_response: '#1d4ed8',
    assistant: '#334155',
    system: '#64748b',
    error: '#b91c1c',
  }), []);

  const appendTrace = useCallback((type, text) => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setTraceLogs((prev) => prev.concat({
      id,
      type,
      text,
      timestamp: new Date().toLocaleTimeString(),
    }));
    return id;
  }, []);

  const updateTraceText = useCallback((entryId, nextText) => {
    setTraceLogs((prev) =>
      prev.map((entry) => (entry.id === entryId ? { ...entry, text: nextText } : entry))
    );
  }, []);

  useEffect(() => {
    if (!traceBodyRef.current || traceMinimized) return;
    traceBodyRef.current.scrollTop = traceBodyRef.current.scrollHeight;
  }, [traceLogs, traceMinimized]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(
      AUTO_SUGGEST_STORAGE_KEY,
      autoSuggestEnabled ? 'true' : 'false',
    );
  }, [autoSuggestEnabled]);

  useEffect(() => {
    if (suggestions.length > previousSuggestionCountRef.current) {
      setSuggestionsMinimized(false);
    }
    previousSuggestionCountRef.current = suggestions.length;
  }, [suggestions.length]);

  useEffect(() => {
    const requestId = typeof autoSuggestRequest?.id === 'string'
      ? autoSuggestRequest.id
      : '';
    if (!requestId || requestId === lastQueuedAutoRequestIdRef.current) {
      return;
    }

    lastQueuedAutoRequestIdRef.current = requestId;
    if (!autoSuggestEnabled) {
      return;
    }

    setPendingAutoRequests((prev) => prev.concat(autoSuggestRequest));
  }, [autoSuggestEnabled, autoSuggestRequest]);

  const streamAssistantResponse = useCallback(async (responseText) => {
    if (!responseText) {
      appendTrace('assistant', '(empty response)');
      return;
    }

    const fullText = String(responseText);
    const entryId = appendTrace('assistant', '');
    let visible = '';
    const chunkSize = Math.max(12, Math.ceil(fullText.length / 90));
    const chunkDelayMs = fullText.length > 1200 ? 6 : RESPONSE_STREAM_DELAY_MS;

    for (let idx = 0; idx < fullText.length; idx += chunkSize) {
      visible += fullText.slice(idx, idx + chunkSize);
      updateTraceText(entryId, visible);
      await wait(chunkDelayMs);
    }
  }, [appendTrace, updateTraceText]);

  const getSuggestionLabel = useCallback((suggestion) => {
    if (!suggestion || typeof suggestion !== 'object') return 'Untitled suggestion';
    return (
      suggestion.displayName
      || suggestion.datasetId
      || suggestion.title
      || 'Untitled suggestion'
    );
  }, []);

  const formatRowCount = useCallback((value) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return null;
    return value.toLocaleString();
  }, []);

  const buildAutoSuggestMessage = useCallback((request) => {
    const datasetId = typeof request?.datasetId === 'string' ? request.datasetId.trim() : '';
    const displayName = typeof request?.displayName === 'string' && request.displayName.trim()
      ? request.displayName.trim()
      : datasetId;
    if (!datasetId) {
      return '';
    }

    return (
      `The user manually added the dataset "${displayName}" ` +
      `(dataset_id="${datasetId}") to the dashboard just now. ` +
      'Review the current canvas and suggest up to 2 complementary datasets that would be useful to add next. ' +
      'Only suggest datasets when there is a clear analytical reason based on the current dashboard. ' +
      'Use suggest_add_dataset_node for each proposed dataset and include a short reason. ' +
      'If there is no strong suggestion, explain that briefly and do not emit tool calls.'
    );
  }, []);

  const submitCopilotMessage = useCallback(async ({
    message,
    traceType = 'user',
    traceText = '',
    clearChatInput = false,
    expandTrace = true,
  }) => {
    const trimmedMessage = typeof message === 'string' ? message.trim() : '';
    if (!trimmedMessage || isSending) return false;

    if (expandTrace) {
      setTraceMinimized(false);
    }
    appendTrace(traceType, traceText || trimmedMessage);
    setIsSending(true);

    try {
      const response = await fetch('http://localhost:8000/api/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmedMessage,
          nodes,
          edges,
          log_stream: true,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err?.detail || 'Failed to send message');
      }

      const payload = await response.json();
      const toolCalls = Array.isArray(payload?.tool_calls) ? payload.tool_calls : [];
      const toolResponses = Array.isArray(payload?.tool_responses) ? payload.tool_responses : [];
      const nextSuggestions = Array.isArray(payload?.suggestions) ? payload.suggestions : [];

      if (toolCalls.length === 0) {
        appendTrace('tool_call', '(no tool calls)');
      } else {
        for (const toolCall of toolCalls) {
          appendTrace('tool_call', JSON.stringify(toolCall));
          await wait(TOOL_EVENT_DELAY_MS);
        }
      }

      if (toolResponses.length === 0) {
        appendTrace('tool_response', '(no tool responses)');
      } else {
        for (const toolResponse of toolResponses) {
          appendTrace('tool_response', JSON.stringify(toolResponse));
          await wait(TOOL_EVENT_DELAY_MS);
        }
      }

      await streamAssistantResponse(payload?.message || '');

      if (payload?.message) {
        console.log('[Copilot]', payload.message);
      }

      if (nextSuggestions.length > 0 && typeof onCopilotSuggestions === 'function') {
        await onCopilotSuggestions(nextSuggestions);
        appendTrace('system', `Queued ${nextSuggestions.length} suggestion(s) for review.`);
      }

      if (clearChatInput) {
        setChatInput('');
      }
      return true;
    } catch (error) {
      console.error('Copilot send error:', error);
      appendTrace('error', error?.message || 'Copilot send error');
      return false;
    } finally {
      setIsSending(false);
    }
  }, [
    appendTrace,
    edges,
    isSending,
    nodes,
    onCopilotSuggestions,
    streamAssistantResponse,
  ]);

  const sendCopilotMessage = useCallback(async () => {
    await submitCopilotMessage({
      message: chatInput,
      traceType: 'user',
      traceText: chatInput.trim(),
      clearChatInput: true,
      expandTrace: true,
    });
  }, [chatInput, submitCopilotMessage]);

  const onChatKeyDown = useCallback((event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      sendCopilotMessage();
    }
  }, [sendCopilotMessage]);

  useEffect(() => {
    if (!autoSuggestEnabled || isSending || pendingAutoRequests.length === 0) {
      return;
    }
    if (autoQueueProcessingRef.current) {
      return;
    }

    const nextRequest = pendingAutoRequests[0];
    const autoMessage = buildAutoSuggestMessage(nextRequest);
    if (!autoMessage) {
      setPendingAutoRequests((prev) => prev.slice(1));
      return;
    }

    autoQueueProcessingRef.current = true;
    const requestId = nextRequest.id;
    const label = nextRequest.displayName || nextRequest.datasetId || 'dataset';

    const runAutoSuggest = async () => {
      try {
        await submitCopilotMessage({
          message: autoMessage,
          traceType: 'system',
          traceText: `Auto-suggest triggered for ${label}.`,
          clearChatInput: false,
          expandTrace: false,
        });
      } finally {
        autoQueueProcessingRef.current = false;
        setPendingAutoRequests((prev) => prev.filter((request) => request.id !== requestId));
      }
    };

    runAutoSuggest();
  }, [
    autoSuggestEnabled,
    buildAutoSuggestMessage,
    isSending,
    pendingAutoRequests,
    submitCopilotMessage,
  ]);

  const handleToggleAutoSuggest = useCallback(() => {
    const nextValue = !autoSuggestEnabled;
    setAutoSuggestEnabled(nextValue);
    if (!nextValue) {
      setPendingAutoRequests([]);
      appendTrace('system', 'Automatic dataset suggestions disabled.');
    } else {
      appendTrace('system', 'Automatic dataset suggestions enabled.');
    }
  }, [appendTrace, autoSuggestEnabled]);

  const handleAcceptClick = useCallback(async (suggestion) => {
    const suggestionId = typeof suggestion?.id === 'string' ? suggestion.id : '';
    if (!suggestionId || resolvingSuggestionId === suggestionId) return;

    setResolvingSuggestionId(suggestionId);
    try {
      const didApply = typeof onAcceptSuggestion === 'function'
        ? await onAcceptSuggestion(suggestion)
        : false;

      if (didApply) {
        appendTrace('system', `Accepted suggestion: ${getSuggestionLabel(suggestion)}.`);
      } else {
        appendTrace('error', `Failed to apply suggestion: ${getSuggestionLabel(suggestion)}.`);
      }
    } catch (error) {
      console.error('Accept suggestion error:', error);
      appendTrace(
        'error',
        error?.message || `Failed to apply suggestion: ${getSuggestionLabel(suggestion)}.`,
      );
    } finally {
      setResolvingSuggestionId((currentId) => (
        currentId === suggestionId ? '' : currentId
      ));
    }
  }, [appendTrace, getSuggestionLabel, onAcceptSuggestion, resolvingSuggestionId]);

  const handleRejectClick = useCallback((suggestion) => {
    if (!suggestion || typeof suggestion !== 'object') return;
    if (resolvingSuggestionId && resolvingSuggestionId === suggestion.id) return;

    const didReject = typeof onRejectSuggestion === 'function'
      ? onRejectSuggestion(suggestion)
      : false;

    if (didReject) {
      appendTrace('system', `Rejected suggestion: ${getSuggestionLabel(suggestion)}.`);
    }
  }, [appendTrace, getSuggestionLabel, onRejectSuggestion, resolvingSuggestionId]);

  return (
    <>
      {suggestions.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            width: 'min(380px, calc(100% - 32px))',
            borderRadius: '16px',
            background: 'rgba(255, 255, 255, 0.88)',
            border: '1px solid rgba(253, 224, 71, 0.45)',
            boxShadow: '0 14px 30px rgba(15, 23, 42, 0.1)',
            backdropFilter: 'blur(12px)',
            overflow: 'hidden',
            zIndex: 45,
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              padding: '10px 12px',
              background: 'linear-gradient(135deg, rgba(254, 249, 195, 0.95), rgba(255, 255, 255, 0.92))',
              borderBottom: '1px solid rgba(253, 224, 71, 0.35)',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#854d0e', fontSize: '12px', fontWeight: 700 }}>
              <Lightbulb size={14} />
              Pending Copilot Suggestions
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  minWidth: '24px',
                  height: '24px',
                  padding: '0 8px',
                  borderRadius: '999px',
                  backgroundColor: '#fef3c7',
                  color: '#92400e',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 700,
                }}
              >
                {suggestions.length}
              </span>
              <button
                onClick={() => setSuggestionsMinimized((prev) => !prev)}
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#92400e',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '2px',
                }}
                title={suggestionsMinimized ? 'Expand suggestions' : 'Minimize suggestions'}
                aria-label={suggestionsMinimized ? 'Expand suggestions' : 'Minimize suggestions'}
              >
                {suggestionsMinimized ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
              </button>
            </span>
          </div>

          {!suggestionsMinimized && (
            <div style={{ maxHeight: '220px', overflowY: 'auto', padding: '10px' }}>
              {suggestions.map((suggestion) => {
                const isResolving = resolvingSuggestionId === suggestion.id;
                const rowCountText = formatRowCount(suggestion.rowCount);

                return (
                  <div
                    key={suggestion.id || suggestion.datasetId}
                    style={{
                      padding: '12px',
                      marginBottom: '12px',
                      backgroundColor: '#ffffff',
                      borderRadius: '8px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
                      transition: 'all 0.2s ease',
                      userSelect: 'none',
                    }}
                    onMouseEnter={(event) => {
                      event.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0, marginRight: '8px' }}>
                        <Database size={16} color="#92400e" style={{ flexShrink: 0 }} />
                        <span
                          title={suggestion.displayName || suggestion.datasetId}
                          style={{
                            fontWeight: '600',
                            fontSize: '0.9rem',
                            color: '#1f2937',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: 'block',
                          }}
                        >
                          {suggestion.displayName || suggestion.datasetId}
                        </span>
                      </div>
                      <span
                        style={{
                          flexShrink: 0,
                          background: '#fef3c7',
                          border: 'none',
                          borderRadius: '4px',
                          padding: '4px 8px',
                          color: '#92400e',
                          fontSize: '0.75rem',
                          fontWeight: '600',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        {suggestion.status || 'pending'}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.78rem', color: '#6b7280', marginBottom: '10px', lineHeight: 1.5 }}>
                      {suggestion.reason || 'Copilot thinks this dataset is relevant to your current analysis.'}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#6b7280', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Layers size={12} />
                        {suggestion.geometryType || 'Unknown Geometry'}
                      </div>
                      <div>{rowCountText ? `${rowCountText} rows` : 'Rows unknown'}</div>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '10px' }}>
                      <span
                        style={{
                          fontSize: '0.7rem',
                          padding: '2px 6px',
                          backgroundColor: '#fff7ed',
                          borderRadius: '4px',
                          color: '#9a3412',
                          border: '1px solid #fed7aa',
                          maxWidth: '100%',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {suggestion.datasetId}
                      </span>
                      {suggestion.colorBy && (
                        <span
                          style={{
                            fontSize: '0.7rem',
                            padding: '2px 6px',
                            backgroundColor: '#ecfeff',
                            borderRadius: '4px',
                            color: '#0f766e',
                            border: '1px solid #a5f3fc',
                            maxWidth: '100%',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          color by {suggestion.colorBy}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                      <button
                        onClick={() => handleRejectClick(suggestion)}
                        disabled={isResolving}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          border: '1px solid #e2e8f0',
                          backgroundColor: '#ffffff',
                          color: '#475569',
                          borderRadius: '4px',
                          padding: '4px 8px',
                          fontSize: '0.75rem',
                          fontWeight: '600',
                          cursor: isResolving ? 'not-allowed' : 'pointer',
                          opacity: isResolving ? 0.6 : 1,
                        }}
                      >
                        <X size={13} />
                        Reject
                      </button>
                      <button
                        onClick={() => handleAcceptClick(suggestion)}
                        disabled={isResolving}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          border: 'none',
                          backgroundColor: isResolving ? '#94a3b8' : '#0f766e',
                          color: '#ffffff',
                          borderRadius: '4px',
                          padding: '4px 8px',
                          fontSize: '0.75rem',
                          fontWeight: '600',
                          cursor: isResolving ? 'not-allowed' : 'pointer',
                        }}
                      >
                        <Check size={13} />
                        {isResolving ? 'Applying...' : 'Accept'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div
        style={{
          position: 'absolute',
          left: '50%',
          bottom: '16px',
          transform: 'translateX(-50%)',
          paddingLeft: '30px',
          boxSizing: 'border-box',
          width: 'min(760px, calc(100% - 40px))',
          zIndex: 40,
        }}
      >
        <div
          style={{
            marginBottom: '8px',
            borderRadius: '12px',
            backgroundColor: 'rgba(255, 255, 255, 0.62)',
            border: '1px solid rgba(203, 213, 225, 0.75)',
            boxShadow: '0 8px 18px rgba(15, 23, 42, 0.08)',
            backdropFilter: 'blur(8px)',
            overflow: 'hidden',
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div
            style={{
              height: '30px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 10px',
              borderBottom: traceMinimized ? 'none' : '1px solid rgba(203, 213, 225, 0.7)',
              backgroundColor: 'rgba(248, 250, 252, 0.55)',
              fontSize: '11px',
              color: '#334155',
              fontWeight: 600,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={13} />
              Agent Trace
            </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <button
              onClick={handleToggleAutoSuggest}
              style={{
                border: 'none',
                borderRadius: '999px',
                background: autoSuggestEnabled ? '#dcfce7' : '#e5e7eb',
                color: autoSuggestEnabled ? '#166534' : '#4b5563',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '4px 10px',
                fontSize: '10px',
                fontWeight: 700,
                whiteSpace: 'nowrap',
              }}
              title={autoSuggestEnabled ? 'Disable auto suggestions' : 'Enable auto suggestions'}
              aria-label={autoSuggestEnabled ? 'Disable auto suggestions' : 'Enable auto suggestions'}
            >
              Auto {autoSuggestEnabled ? 'On' : 'Off'}
            </button>
            <button
              onClick={() => setTraceLogs([])}
              style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#64748b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '2px',
                }}
                title="Clear trace"
                aria-label="Clear trace"
              >
                <Trash2 size={12} />
              </button>
              <button
                onClick={() => setTraceMinimized((prev) => !prev)}
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#64748b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '2px',
                }}
                title={traceMinimized ? 'Expand trace' : 'Minimize trace'}
                aria-label={traceMinimized ? 'Expand trace' : 'Minimize trace'}
              >
                {traceMinimized ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            </span>
          </div>

          {!traceMinimized && (
            <div
              ref={traceBodyRef}
              style={{
                maxHeight: '154px',
                overflowY: 'auto',
                padding: '8px 10px',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                fontSize: '11px',
                lineHeight: 1.5,
                color: '#334155',
              }}
            >
              {traceLogs.length === 0 ? (
                <div style={{ color: '#64748b' }}>No events yet.</div>
              ) : (
                traceLogs.map((entry) => (
                  <div key={entry.id} style={{ marginBottom: '4px', color: traceColorMap[entry.type] || '#334155' }}>
                    <span style={{ opacity: 0.65, marginRight: '6px' }}>[{entry.timestamp}]</span>
                    <strong style={{ fontWeight: 600, marginRight: '6px' }}>{entry.type}</strong>
                    <span>{entry.text}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#ffffff',
            border: '1px solid #dbe3ee',
            borderRadius: '999px',
            padding: '6px 6px 6px 14px',
            boxShadow: '0 10px 25px rgba(15, 23, 42, 0.08)',
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={onChatKeyDown}
            placeholder="Ask Copilot..."
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize: '13px',
              color: '#1e293b',
            }}
          />
          <button
            onClick={sendCopilotMessage}
            disabled={isSending || !chatInput.trim()}
            title={isSending ? 'Searching datasets...' : 'Send message'}
            style={{
              gap: '6px',
              width: isSending ? 'auto' : '34px',
              height: '34px',
              padding: isSending ? '0 10px' : 0,
              border: 'none',
              borderRadius: '999px',
              backgroundColor: isSending ? '#0ea5e9' : '#0f172a',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: isSending ? 'not-allowed' : 'pointer',
              flexShrink: 0,
              outline: 'none',
              lineHeight: 0,
              transition: 'all 0.2s ease-in-out',
              fontSize: '12px',
              fontWeight: '500',
            }}
            aria-label={isSending ? 'Processing request' : 'Send message to Copilot'}
          >
            {isSending ? (
              <>
                <Loader2 size={16} strokeWidth={2.4} style={{ animation: 'spin 0.8s linear infinite' }} />
                <span>Searching…</span>
              </>
            ) : (
              <ArrowRight size={17} strokeWidth={2.6} color="#ffffff" style={{ display: 'block' }} />
            )}
          </button>
          <style>{`
            @keyframes spin {
              from { transform: rotate(0deg); }
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    </>
  );
};

export default FloatingCopilotInput;
