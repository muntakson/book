import React, { useState, useEffect } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { io, Socket } from 'socket.io-client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '@xterm/xterm/css/xterm.css';
import './App.css';

interface User {
  id: number;
  username: string;
}

interface Project {
  id: number;
  name: string;
  book_idea: string;
  adapted_prompt: string | null;
  user_feedback: string | null;
  generated_content: string | null;
  conversation_history: string | null;
  model_used: string | null;
  tokens_used: number | null;
  stage: string | null;
  stage_status: string | null;
  created_at: string;
  updated_at: string;
}

interface AdminProject extends Project {
  user_id: number;
  owner_username: string;
}

interface ProgressLog {
  id: number;
  stage: string;
  message: string;
  level: string;
  created_at: string;
}

interface ChapterInfo {
  chapter_number: number;
  title: string;
  word_count: number;
}

interface GeneratedContentInfo {
  folder_location: string;
  total_chapters: number;
  total_words: number;
  chapters: ChapterInfo[];
}

interface UserStats {
  id: number;
  username: string;
  created_at: string;
  project_count: number;
  total_tokens: number;
}

interface DashboardStats {
  total_users: number;
  total_projects: number;
  total_prompts_generated: number;
  total_tokens_used: number;
  recent_projects: AdminProject[];
}

interface BookFile {
  filename: string;
  path: string;
  size: number;
  modified: string;
}

interface BookGroup {
  project_name: string;
  output_path: string;
  books: BookFile[];
}

interface PdfStatus {
  has_pdf: boolean;
  pdf_path: string | null;
  pdf_size: number | null;
  has_korean_pdf: boolean;
  korean_pdf_path: string | null;
  korean_pdf_size: number | null;
  stage: string;
  stage_status: string;
}

interface LLMModelInfo {
  provider: string;
  model_id: string;
  display_name: string;
  description: string;
  available: boolean;
}

interface UserSettings {
  llm_provider: string;
  llm_model: string;
  translation_system_prompt: string;
  temperature: string;
}

interface VoiceFile {
  filename: string;
  path: string;
  size: number;
  modified: string;
}

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<'list' | 'create' | 'detail' | 'admin' | 'terminal' | 'published_books' | 'workflow' | 'records'>('list');
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Login form
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isSignup, setIsSignup] = useState(false);
  const [signupName, setSignupName] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupAffiliation, setSignupAffiliation] = useState('');

  // Create project form
  const [projectName, setProjectName] = useState('');
  const [bookIdea, setBookIdea] = useState('');

  // Admin state
  const [adminStats, setAdminStats] = useState<DashboardStats | null>(null);
  const [allUsers, setAllUsers] = useState<UserStats[]>([]);
  const [allProjects, setAllProjects] = useState<AdminProject[]>([]);
  const [editingProject, setEditingProject] = useState<AdminProject | null>(null);
  const [bookGroups, setBookGroups] = useState<BookGroup[]>([]);
  const [projectLogs, setProjectLogs] = useState<Map<number, ProgressLog[]>>(new Map());
  const [expandedLogRows, setExpandedLogRows] = useState<Set<number>>(new Set());

  // Generated content state
  const [contentInfo, setContentInfo] = useState<GeneratedContentInfo | null>(null);

  // User project logs state
  const [userProjectLogs, setUserProjectLogs] = useState<ProgressLog[]>([]);
  const [showUserLogs, setShowUserLogs] = useState(false);
  const [userLogPolling, setUserLogPolling] = useState<number | null>(null);

  // Plan collapse state
  const [isPlanCollapsed, setIsPlanCollapsed] = useState(false);

  // User feedback state
  const [userFeedback, setUserFeedback] = useState('');
  const [feedbackSaved, setFeedbackSaved] = useState(false);

  // Chapter refinement chatbox state
  const [chatPrompt, setChatPrompt] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<Array<{role: string, content: string}>>([]);

  // PDF status state
  const [pdfStatus, setPdfStatus] = useState<PdfStatus | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Settings state
  const [showSettings, setShowSettings] = useState(false);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [availableModels, setAvailableModels] = useState<LLMModelInfo[]>([]);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [isSystemPromptExpanded, setIsSystemPromptExpanded] = useState(false);

  // Voice files state
  const [voiceFiles, setVoiceFiles] = useState<VoiceFile[]>([]);
  const [voiceFileUploading, setVoiceFileUploading] = useState(false);

  useEffect(() => {
    if (token) {
      fetchUser();
      fetchProjects();
      fetchUserSettings();
      fetchAvailableModels();
    }
  }, [token]);

  // Terminal initialization with Socket.IO
  useEffect(() => {
    if (view === 'terminal' && user?.username === 'admin' && token) {
      const terminalElement = document.getElementById('terminal');
      if (!terminalElement) return;

      // Clear any existing terminal
      terminalElement.innerHTML = '';

      // Initialize xterm
      const term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        theme: {
          background: '#1e1e1e',
          foreground: '#d4d4d4',
          cursor: '#ffffff',
        },
        rows: 30,
        cols: 100,
        scrollback: 1000,
      });

      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(terminalElement);
      fitAddon.fit();

      // Connect to Socket.IO terminal server through Nginx proxy
      // Use same domain, Nginx will proxy /socket.io/ to port 8087
      const socket: Socket = io(window.location.origin, {
        path: '/socket.io/',
        auth: {
          token: token
        },
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
      });

      term.writeln('\x1b[36mConnecting to terminal server...\x1b[0m');

      // Connection established
      socket.on('connect', () => {
        console.log('Terminal connected:', socket.id);
        term.writeln('\x1b[32m✓ Connected to terminal server\x1b[0m');
        term.focus();
      });

      // Receive output from PTY
      socket.on('output', (data: string) => {
        term.write(data);
      });

      // Handle connection errors
      socket.on('connect_error', (error) => {
        console.error('Terminal connection error:', error.message);
        term.writeln(`\r\n\x1b[31m✗ Connection error: ${error.message}\x1b[0m`);
        term.writeln('\x1b[33mRetrying...\x1b[0m');
      });

      // Handle authentication errors
      socket.on('error', (error) => {
        console.error('Terminal error:', error);
        term.writeln(`\r\n\x1b[31m✗ Error: ${error}\x1b[0m`);
      });

      // Handle PTY exit
      socket.on('exit', ({ exitCode, signal }) => {
        console.log('PTY exited:', exitCode, signal);
        term.writeln(`\r\n\x1b[33mTerminal session ended (exit code: ${exitCode})\x1b[0m`);
      });

      // Handle disconnection
      socket.on('disconnect', (reason) => {
        console.log('Terminal disconnected:', reason);
        term.writeln(`\r\n\x1b[33mDisconnected: ${reason}\x1b[0m`);
      });

      // Send user input to PTY
      term.onData((data) => {
        if (socket.connected) {
          socket.emit('input', data);
        }
      });

      // Handle terminal resize
      const handleResize = () => {
        fitAddon.fit();
        if (socket.connected) {
          socket.emit('resize', {
            cols: term.cols,
            rows: term.rows
          });
        }
      };

      // Initial resize after a brief delay to ensure proper layout
      setTimeout(() => handleResize(), 100);

      window.addEventListener('resize', handleResize);

      // Cleanup on unmount
      return () => {
        console.log('Cleaning up terminal...');
        window.removeEventListener('resize', handleResize);
        socket.disconnect();
        term.dispose();
      };
    }
  }, [view, user, token]);

  const fetchUser = async () => {
    try {
      const res = await fetch('/api/me', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        logout();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchProjects = async () => {
    try {
      const res = await fetch('/api/projects', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchUserSettings = async () => {
    try {
      const res = await fetch('/api/settings', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUserSettings(data);
      }
    } catch (err) {
      console.error('Error fetching settings:', err);
    }
  };

  const fetchAvailableModels = async () => {
    try {
      const res = await fetch('/api/available-models');
      if (res.ok) {
        const data = await res.json();
        setAvailableModels(data);
      }
    } catch (err) {
      console.error('Error fetching models:', err);
    }
  };

  const fetchVoiceFiles = async () => {
    try {
      const res = await fetch('/api/voice-files', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVoiceFiles(data);
      }
    } catch (err) {
      console.error('Error fetching voice files:', err);
    }
  };

  const handleVoiceFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setVoiceFileUploading(true);
    setError(null);

    try {
      for (const file of Array.from(files)) {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('/api/voice-files/upload', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        });

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || 'Upload failed');
        }
      }

      // Refresh the file list
      await fetchVoiceFiles();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setVoiceFileUploading(false);
      // Reset the file input
      e.target.value = '';
    }
  };

  const handleDeleteVoiceFile = async (filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;

    try {
      const res = await fetch(`/api/voice-files/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Delete failed');
      }

      await fetchVoiceFiles();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSaveSettings = async () => {
    if (!userSettings) return;

    setSettingsLoading(true);
    setSettingsSaved(false);

    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(userSettings)
      });

      if (res.ok) {
        const data = await res.json();
        setUserSettings(data);
        setSettingsSaved(true);
        setTimeout(() => setSettingsSaved(false), 3000);
      } else {
        throw new Error('Failed to save settings');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleModelChange = (modelId: string) => {
    const model = availableModels.find(m => m.model_id === modelId);
    if (model && userSettings) {
      setUserSettings({
        ...userSettings,
        llm_provider: model.provider,
        llm_model: model.model_id
      });
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Login failed');
      }

      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setUser({ id: data.user_id, username: data.username });
      setPassword('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password,
          name: signupName,
          email: signupEmail,
          affiliation: signupAffiliation
        })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Signup failed');
      }

      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setUser({ id: data.user_id, username: data.username });
      setPassword('');
      setIsSignup(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    setProjects([]);
    setView('list');
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ name: projectName, book_idea: bookIdea })
      });

      if (!res.ok) throw new Error('Failed to create project');

      const project = await res.json();
      setProjects([project, ...projects]);
      setProjectName('');
      setBookIdea('');
      setView('list');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePrompt = async (projectId: number) => {
    setLoading(true);
    setError(null);

    try {
      // Different endpoints for admin vs regular users
      const endpoint = user?.username === 'admin' ? '/api/adapt-prompt' : '/api/generate-plan';

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ project_id: projectId })
      });

      if (!res.ok) throw new Error('Failed to generate');

      const data = await res.json();

      // Fetch fresh project data to get updated stage info
      const projectRes = await fetch(`/api/projects/${projectId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (projectRes.ok) {
        const updatedProject = await projectRes.json();
        setSelectedProject(updatedProject);
        // Also refresh the projects list
        fetchProjects();
      } else {
        // Fallback: manually update with data from response
        await fetchProjects();
        const updated = projects.find(p => p.id === projectId);
        if (updated) {
          setSelectedProject({
            ...updated,
            adapted_prompt: data.adapted_prompt || data.plan,
            model_used: data.model,
            tokens_used: data.tokens_used,
            stage: '1단계',
            stage_status: 'pending'
          });
        }
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveFeedback = async (projectId: number) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/save-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ project_id: projectId, feedback: userFeedback })
      });

      if (!res.ok) throw new Error('Failed to save feedback');

      setFeedbackSaved(true);

      // Refresh the project to get updated data
      await fetchProjects();
      const updated = projects.find(p => p.id === projectId);
      if (updated) {
        setSelectedProject(updated);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefineChapter = async (projectId: number) => {
    if (!chatPrompt.trim()) return;

    setChatLoading(true);
    setError(null);

    try {
      // Add user message to chat history
      setChatHistory(prev => [...prev, { role: 'user', content: chatPrompt }]);

      const res = await fetch('/api/refine-chapter', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ project_id: projectId, user_prompt: chatPrompt })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.message || 'Failed to refine chapter');
      }

      if (!data.success) {
        throw new Error(data.message);
      }

      // Add AI response to chat history
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: data.message + `\n\nChapter ${data.chapter_number} has been updated. Check the Progress Logs for details.`
      }]);

      // Clear input
      setChatPrompt('');

      // Refresh project and logs
      await fetchProjects();
      fetchUserProjectLogs(projectId);

      const updated = projects.find(p => p.id === projectId);
      if (updated) {
        setSelectedProject(updated);
      }
    } catch (err: any) {
      setError(err.message);
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleDeleteProject = async (projectId: number) => {
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!res.ok) throw new Error('Failed to delete project');

      setProjects(projects.filter(p => p.id !== projectId));
      if (selectedProject?.id === projectId) {
        setSelectedProject(null);
        setView('list');
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const viewProjectDetail = async (project: Project) => {
    setSelectedProject(project);
    setView('detail');

    // Fetch content info if English writing is completed
    if (project.stage_status === 'completed' && project.generated_content) {
      try {
        const res = await fetch(`/api/projects/${project.id}/content-info`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const info = await res.json();
          setContentInfo(info);
        }
      } catch (err) {
        console.error('Error fetching content info:', err);
      }
    } else {
      setContentInfo(null);
    }

    // Fetch PDF status for Stage 4 and Stage 5 projects
    if (project.stage === '4단계' || project.stage === '5단계') {
      fetchPdfStatus(project.id);
      // Also fetch logs
      fetchUserProjectLogs(project.id);
    } else {
      setPdfStatus(null);
    }
  };

  const openChapter = (projectId: number, chapterNumber: number) => {
    const url = `/api/projects/${projectId}/chapters/${chapterNumber}?token=${encodeURIComponent(token || '')}`;
    window.open(url, '_blank');
  };

  // Admin functions
  const fetchAdminStats = async () => {
    try {
      const res = await fetch('/api/admin/stats', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAdminStats(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAllUsers = async () => {
    try {
      const res = await fetch('/api/admin/users', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAllUsers(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAllProjects = async () => {
    try {
      const res = await fetch('/api/admin/projects', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAllProjects(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchBooks = async () => {
    try {
      // Use public endpoint for published books
      const res = await fetch('/api/books', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setBookGroups(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const openBook = (path: string) => {
    try {
      // Open PDF directly from API endpoint with auth token in URL
      // This allows browser's native PDF viewer to handle it properly including downloads
      const url = `/api/books/view?path=${encodeURIComponent(path)}&token=${encodeURIComponent(token || '')}`;
      window.open(url, '_blank');
    } catch (err) {
      console.error('Error opening PDF:', err);
      setError('Failed to open PDF');
    }
  };

  const handleAdminUpdateProject = async (projectId: number, updates: Partial<AdminProject>) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/admin/projects/${projectId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(updates)
      });

      if (!res.ok) throw new Error('Failed to update project');

      await fetchAllProjects();
      setEditingProject(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAdminDeleteProject = async (projectId: number) => {
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      const res = await fetch(`/api/admin/projects/${projectId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!res.ok) throw new Error('Failed to delete project');

      await fetchAllProjects();
      await fetchAdminStats();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleProceedStage = async (projectId: number) => {
    if (!confirm('Proceed to next stage? This will start the book writing process.')) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/admin/proceed-stage', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ project_id: projectId })
      });

      if (!res.ok) throw new Error('Failed to proceed stage');

      // Refresh projects
      await fetchAllProjects();

      // Start polling for logs
      fetchProjectLogs(projectId);
      const intervalId = setInterval(() => {
        fetchProjectLogs(projectId);
        fetchAllProjects();
      }, 3000);

      // Store interval ID for cleanup
      (window as any)[`logPoll_${projectId}`] = intervalId;

    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchProjectLogs = async (projectId: number) => {
    try {
      const res = await fetch(`/api/admin/projects/${projectId}/logs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      // Stop polling if project not found
      if (res.status === 404) {
        const intervalId = (window as any)[`logPoll_${projectId}`];
        if (intervalId) {
          clearInterval(intervalId);
          delete (window as any)[`logPoll_${projectId}`];
        }
        return;
      }
      if (res.ok) {
        const logs = await res.json();
        setProjectLogs(prev => new Map(prev).set(projectId, logs));
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  const toggleLogExpansion = (projectId: number) => {
    setExpandedLogRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(projectId)) {
        newSet.delete(projectId);
        // Stop polling when collapsed
        const intervalId = (window as any)[`logPoll_${projectId}`];
        if (intervalId) {
          clearInterval(intervalId);
          delete (window as any)[`logPoll_${projectId}`];
        }
      } else {
        newSet.add(projectId);
        // Start polling when expanded
        fetchProjectLogs(projectId);
      }
      return newSet;
    });
  };

  // User functions for proceeding stages
  const handleUserProceedStage = async (projectId: number) => {
    const project = projects.find(p => p.id === projectId);
    let confirmMessage = 'Proceed to next stage?';

    if (project?.stage === '1단계') {
      confirmMessage = 'Proceed to Stage 2? This will start writing your book chapters.';
    } else if (project?.stage === '2단계') {
      confirmMessage = 'Proceed to Stage 3? This will perform fact-checking and critical review.';
    } else if (project?.stage === '3단계') {
      confirmMessage = 'Proceed to Stage 4? This will generate the English PDF.';
    } else if (project?.stage === '4단계') {
      confirmMessage = 'Proceed to Stage 5? This will translate your book to Korean and generate Korean PDF.';
    }

    if (!confirm(confirmMessage)) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/proceed-stage', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ project_id: projectId })
      });

      if (!res.ok) {
        const errorData = await res.json();
        // Refresh project data to show current state
        await fetchProjects();
        const updated = projects.find(p => p.id === projectId);
        if (updated) {
          setSelectedProject(updated);
        }
        throw new Error(errorData.detail || 'Failed to proceed stage');
      }

      // Refresh project list
      await fetchProjects();

      // Update selected project with fresh data
      const updatedProjects = await fetch('/api/projects', {
        headers: { 'Authorization': `Bearer ${token}` }
      }).then(r => r.json());

      const updatedProject = updatedProjects.find((p: Project) => p.id === projectId);
      if (updatedProject) {
        setSelectedProject(updatedProject);

        // Fetch content info if available
        if (updatedProject.generated_content) {
          try {
            const contentRes = await fetch(`/api/projects/${projectId}/content-info`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            if (contentRes.ok) {
              const info = await contentRes.json();
              setContentInfo(info);
            }
          } catch (err) {
            console.error('Error fetching content info:', err);
          }
        }
      }

      // Start showing logs automatically
      setShowUserLogs(true);
      fetchUserProjectLogs(projectId);

      // Start polling for logs every 3 seconds
      const intervalId = window.setInterval(async () => {
        fetchUserProjectLogs(projectId);

        // Update project status only if stage_status changed
        const freshProjectRes = await fetch(`/api/projects/${projectId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).catch(() => null);

        // Stop polling and navigate back if project not found (404)
        if (freshProjectRes && freshProjectRes.status === 404) {
          clearInterval(intervalId);
          setUserLogPolling(null);
          setSelectedProject(null);
          setShowUserLogs(false);
          setView('list');
          fetchProjects();
          return;
        }

        if (freshProjectRes && freshProjectRes.ok) {
          const freshProject = await freshProjectRes.json();
          // Only update if status actually changed to avoid flickering
          setSelectedProject((prev: Project | null) => {
            if (!prev) return freshProject;
            if (prev.stage_status !== freshProject.stage_status ||
                prev.stage !== freshProject.stage ||
                prev.generated_content !== freshProject.generated_content) {
              // Also fetch PDF status when Stage 4 or Stage 5 completes
              if ((freshProject.stage === '4단계' || freshProject.stage === '5단계') &&
                  freshProject.stage_status === 'completed') {
                fetchPdfStatus(projectId);
              }
              return freshProject;
            }
            return prev;
          });
        }
      }, 3000);

      setUserLogPolling(intervalId);

    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserProjectLogs = async (projectId: number) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/logs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      // Stop polling if project not found
      if (res.status === 404) {
        if (userLogPolling) {
          clearInterval(userLogPolling);
          setUserLogPolling(null);
        }
        setSelectedProject(null);
        setShowUserLogs(false);
        setView('list');
        fetchProjects();
        return;
      }
      if (res.ok) {
        const logs = await res.json();
        setUserProjectLogs(logs);
        // Don't update selectedProject here - let the polling interval handle it
      }
    } catch (err) {
      console.error('Error fetching user logs:', err);
    }
  };

  const fetchPdfStatus = async (projectId: number) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/pdf-status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const status = await res.json();
        setPdfStatus(status);
      }
    } catch (err) {
      console.error('Error fetching PDF status:', err);
    }
  };

  const handleDownloadPdf = async (projectId: number) => {
    setPdfLoading(true);
    try {
      const url = `/api/projects/${projectId}/download-pdf?token=${encodeURIComponent(token || '')}`;
      window.open(url, '_blank');
    } catch (err) {
      console.error('Error downloading PDF:', err);
      setError('Failed to download PDF');
    } finally {
      setPdfLoading(false);
    }
  };

  const handleDownloadKoreanPdf = async (projectId: number) => {
    setPdfLoading(true);
    try {
      const url = `/api/projects/${projectId}/download-korean-pdf?token=${encodeURIComponent(token || '')}`;
      window.open(url, '_blank');
    } catch (err) {
      console.error('Error downloading Korean PDF:', err);
      setError('Failed to download Korean PDF');
    } finally {
      setPdfLoading(false);
    }
  };

  const handleDownloadMarkdown = async (projectId: number) => {
    try {
      const url = `/api/projects/${projectId}/download-markdown?token=${encodeURIComponent(token || '')}`;
      window.open(url, '_blank');
    } catch (err) {
      console.error('Error downloading markdown:', err);
      setError('Failed to download markdown');
    }
  };

  const handleDownloadKoreanMarkdown = async (projectId: number) => {
    try {
      const url = `/api/projects/${projectId}/download-korean-markdown?token=${encodeURIComponent(token || '')}`;
      window.open(url, '_blank');
    } catch (err) {
      console.error('Error downloading Korean markdown:', err);
      setError('Failed to download Korean markdown');
    }
  };

  const toggleUserLogs = () => {
    if (showUserLogs && userLogPolling) {
      // Stop polling when hiding logs
      clearInterval(userLogPolling);
      setUserLogPolling(null);
    } else if (!showUserLogs && selectedProject) {
      // Start polling when showing logs
      fetchUserProjectLogs(selectedProject.id);
    }
    setShowUserLogs(!showUserLogs);
  };

  // Cleanup polling on unmount or view change
  React.useEffect(() => {
    return () => {
      if (userLogPolling) {
        clearInterval(userLogPolling);
      }
    };
  }, [userLogPolling]);

  // Login View
  if (!token) {
    return (
      <div className="app-container">
        <div className="login-container">
          <div className="login-box">
            <h1>📚 디지탈 아카이브 출판사</h1>
            <p className="subtitle">AI 기반 도서 프롬프트 어댑터</p>

            {!isSignup && (
              <p className="demo-credentials" style={{ textAlign: 'center', color: '#7f8c8d', fontSize: '0.9em', marginTop: '-8px', marginBottom: '12px' }}>
                default id=<strong>bob</strong>, pwd=<strong>q1</strong>
              </p>
            )}

            <form onSubmit={isSignup ? handleSignup : handleLogin} className="login-form">
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={isSignup ? "Choose a username (3+ chars)" : "Enter your username"}
                  required
                />
              </div>

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={isSignup ? "Choose a password (2+ chars)" : "Enter password"}
                  required
                />
              </div>

              {isSignup && (
                <>
                  <div className="form-group">
                    <label>이름 (Name)</label>
                    <input
                      type="text"
                      value={signupName}
                      onChange={(e) => setSignupName(e.target.value)}
                      placeholder="Enter your name"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>이메일 (Email)</label>
                    <input
                      type="email"
                      value={signupEmail}
                      onChange={(e) => setSignupEmail(e.target.value)}
                      placeholder="Enter your email"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>소속 (Affiliation)</label>
                    <input
                      type="text"
                      value={signupAffiliation}
                      onChange={(e) => setSignupAffiliation(e.target.value)}
                      placeholder="Enter your affiliation"
                      required
                    />
                  </div>
                </>
              )}

              {error && <div className="error-message">{error}</div>}

              <button type="submit" className="primary-button" disabled={loading}>
                {loading ? (isSignup ? 'Creating account...' : 'Logging in...') : (isSignup ? '📝 Sign Up' : '🔐 Login')}
              </button>
            </form>

            <div className="auth-toggle" style={{ marginTop: '16px', textAlign: 'center' }}>
              {isSignup ? (
                <p>
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => { setIsSignup(false); setError(null); }}
                    className="link-button"
                    style={{ background: 'none', border: 'none', color: '#3498db', cursor: 'pointer', textDecoration: 'underline' }}
                  >
                    Login
                  </button>
                </p>
              ) : (
                <p>
                  Don't have an account?{' '}
                  <button
                    type="button"
                    onClick={() => { setIsSignup(true); setError(null); }}
                    className="link-button"
                    style={{ background: 'none', border: 'none', color: '#3498db', cursor: 'pointer', textDecoration: 'underline' }}
                  >
                    Sign Up
                  </button>
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Main App View
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="header-left">
            <h1 onClick={() => setView('list')} className="site-title">📚 디지탈 아카이브 출판사</h1>
            <button
              onClick={() => {
                setView('published_books');
                fetchBooks();
              }}
              className="nav-link-button"
            >
              📖 우리가 펴낸 책
            </button>
            <button
              onClick={() => setView('workflow')}
              className="nav-link-button"
            >
              📋 출판절차
            </button>
            <button
              onClick={() => {
                setView('records');
                fetchVoiceFiles();
              }}
              className="nav-link-button"
            >
              🎙️ Records
            </button>
          </div>
          <div className="header-actions">
            <span className="user-info">👤 {user?.username}</span>
            <button
              onClick={() => setShowSettings(true)}
              className="settings-button"
              title="Settings"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
            </button>
            {user?.username === 'admin' && (
              <button
                onClick={() => {
                  setView('admin');
                  fetchAdminStats();
                  fetchAllUsers();
                  fetchAllProjects();
                  fetchBooks();
                }}
                className="secondary-button-small"
              >
                Admin Dashboard
              </button>
            )}
            <button onClick={logout} className="secondary-button-small">Logout</button>
          </div>
        </div>
      </header>

      {/* Settings Modal */}
      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
            <div className="settings-header">
              <h2>LLM Settings</h2>
              <button className="close-button" onClick={() => setShowSettings(false)}>×</button>
            </div>

            <div className="settings-content">
              {/* Model Selector */}
              <div className="form-group">
                <label>LLM Model for Translation</label>
                <select
                  value={userSettings?.llm_model || 'llama-3.3-70b-versatile'}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className="model-select"
                >
                  {/* Group models by provider */}
                  <optgroup label="Groq (Fast) ✓">
                    {availableModels.filter(m => m.provider === 'groq').map(model => (
                      <option key={model.model_id} value={model.model_id}>
                        {model.available ? '✓ ' : '✗ '}{model.display_name}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="DeepSeek">
                    {availableModels.filter(m => m.provider === 'deepseek').map(model => (
                      <option key={model.model_id} value={model.model_id} disabled={!model.available}>
                        {model.available ? '✓ ' : '✗ '}{model.display_name}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Korean Specialized">
                    {availableModels.filter(m => ['upstage', 'exaone'].includes(m.provider)).map(model => (
                      <option key={model.model_id} value={model.model_id} disabled={!model.available}>
                        {model.available ? '✓ ' : '✗ '}{model.display_name}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Qwen (Alibaba)">
                    {availableModels.filter(m => m.provider === 'qwen').map(model => (
                      <option key={model.model_id} value={model.model_id} disabled={!model.available}>
                        {model.available ? '✓ ' : '✗ '}{model.display_name}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Other Chinese Models">
                    {availableModels.filter(m => ['glm', 'kimi'].includes(m.provider)).map(model => (
                      <option key={model.model_id} value={model.model_id} disabled={!model.available}>
                        {model.available ? '✓ ' : '✗ '}{model.display_name}
                      </option>
                    ))}
                  </optgroup>
                </select>
                <p className="field-hint">
                  {availableModels.find(m => m.model_id === userSettings?.llm_model)?.description || 'Select a model for Korean translation'}
                </p>
                {!availableModels.find(m => m.model_id === userSettings?.llm_model)?.available && (
                  <p className="field-warning">Selected model requires API key. Will fallback to Groq Llama.</p>
                )}
              </div>

              {/* Temperature */}
              <div className="form-group">
                <label>Temperature: {userSettings?.temperature || '0.3'}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={userSettings?.temperature || '0.3'}
                  onChange={(e) => setUserSettings(prev => prev ? {...prev, temperature: e.target.value} : null)}
                  className="temperature-slider"
                />
                <p className="field-hint">Lower = more consistent, Higher = more creative</p>
              </div>

              {/* System Prompt - Collapsible */}
              <div className="form-group">
                <div
                  className="collapsible-header"
                  onClick={() => setIsSystemPromptExpanded(!isSystemPromptExpanded)}
                >
                  <label>Translation System Prompt</label>
                  <span className="collapse-icon">{isSystemPromptExpanded ? '▼' : '▶'}</span>
                </div>
                {isSystemPromptExpanded && (
                  <div className="system-prompt-container">
                    <textarea
                      value={userSettings?.translation_system_prompt || ''}
                      onChange={(e) => setUserSettings(prev => prev ? {...prev, translation_system_prompt: e.target.value} : null)}
                      className="system-prompt-textarea"
                      rows={15}
                      placeholder="Enter custom system prompt for translation..."
                    />
                    <p className="field-hint">
                      This prompt instructs the AI how to translate. Edit to fix translation issues like Chinese characters or code appearing.
                    </p>
                    <button
                      className="secondary-button-small"
                      onClick={() => setUserSettings(prev => prev ? {
                        ...prev,
                        translation_system_prompt: `You are a professional Korean translator specializing in educational books.

TRANSLATION GUIDELINES:
- Translate all English text to natural, fluent Korean (한글)
- Use formal Korean style (존댓말/합쇼체)
- Keep technical terms in English with Korean explanation in parentheses when first introduced
- Preserve all markdown formatting (##, **, -, code blocks, etc.)
- Keep code examples in English but translate comments to Korean
- Maintain the educational tone suitable for Korean readers
- Do NOT add any translator notes or explanations outside the content
- Do NOT output Chinese characters under any circumstances
- Do NOT include random code snippets that are not part of the original content`
                      } : null)}
                    >
                      Reset to Default
                    </button>
                  </div>
                )}
              </div>

              {/* Save Button */}
              <div className="settings-actions">
                {settingsSaved && <span className="save-success">Settings saved!</span>}
                <button
                  className="primary-button"
                  onClick={handleSaveSettings}
                  disabled={settingsLoading}
                >
                  {settingsLoading ? 'Saving...' : 'Save Settings'}
                </button>
                <button
                  className="secondary-button-small"
                  onClick={() => setShowSettings(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <main className="main-content">
        {error && <div className="error-banner">{error}</div>}

        {/* Project List View */}
        {view === 'list' && (
          <div className="projects-view">
            <div className="view-header">
              <h2>My Projects</h2>
              <button onClick={() => setView('create')} className="primary-button">
                ➕ New Project
              </button>
            </div>

            {projects.length === 0 ? (
              <div className="empty-state">
                <p>No projects yet. Create your first project to get started!</p>
              </div>
            ) : (
              <div className="projects-grid">
                {projects.map(project => (
                  <div key={project.id} className="project-card">
                    <div className="project-card-header">
                      <span className="project-id">ID: {project.id}</span>
                      <span className="project-tokens">
                        {project.tokens_used ? `${project.tokens_used.toLocaleString()} tokens` : '0 tokens'}
                      </span>
                      <span className="project-cost">
                        ${project.tokens_used ? ((project.tokens_used / 1_000_000) * 0.70).toFixed(4) : '0.0000'}
                      </span>
                    </div>
                    <h3>{project.name}</h3>
                    <p className="project-idea">{project.book_idea.substring(0, 100)}...</p>
                    <div className="project-meta">
                      {project.adapted_prompt ? (
                        <span className="status-badge success">✅ Generated</span>
                      ) : (
                        <span className="status-badge pending">⏳ Not generated</span>
                      )}
                      <span className="date">{new Date(project.updated_at).toLocaleDateString()}</span>
                    </div>
                    <div className="project-actions">
                      <button onClick={() => viewProjectDetail(project)} className="secondary-button-small">
                        View
                      </button>
                      <button onClick={() => handleDeleteProject(project.id)} className="danger-button-small">
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Create Project View */}
        {view === 'create' && (
          <div className="create-view">
            <div className="view-header">
              <h2>Create New Project</h2>
              <button onClick={() => setView('list')} className="secondary-button">
                ← Back to Projects
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="create-form">
              <div className="form-group">
                <label>Project Name</label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="e.g., Hydroponic AI Book"
                  required
                />
              </div>

              <div className="form-group">
                <label>Book Idea</label>
                <textarea
                  value={bookIdea}
                  onChange={(e) => setBookIdea(e.target.value)}
                  placeholder="Describe your book idea in detail..."
                  rows={8}
                  required
                />
              </div>

              <button type="submit" className="primary-button" disabled={loading}>
                {loading ? 'Creating...' : '✨ Create Project'}
              </button>
            </form>
          </div>
        )}

        {/* Project Detail View */}
        {view === 'detail' && selectedProject && (
          <div className="detail-view">
            <div className="view-header">
              <div>
                <h2>{selectedProject.name}</h2>
                <span className="project-id-badge">Project ID: {selectedProject.id}</span>
              </div>
              <button onClick={() => setView('list')} className="secondary-button">
                ← Back to Projects
              </button>
            </div>

            <div className="detail-content">
              <section className="detail-section">
                <h3>Book Idea</h3>
                <p className="book-idea-text">{selectedProject.book_idea}</p>
              </section>

              {!selectedProject.adapted_prompt ? (
                <section className="detail-section">
                  <button
                    onClick={() => handleGeneratePrompt(selectedProject.id)}
                    className="primary-button"
                    disabled={loading}
                  >
                    {loading
                      ? (user?.username === 'admin' ? '⏳ Generating with Groq AI...' : '⏳ 계획 생성 중...')
                      : (user?.username === 'admin' ? '🚀 Generate Adapted Prompt' : '📝 계획 생성하기')
                    }
                  </button>
                </section>
              ) : (
                <>
                  <section className="detail-section">
                    <div className="model-info-bar">
                      <span>Model: {selectedProject.model_used}</span>
                      <span>Tokens: {selectedProject.tokens_used?.toLocaleString()}</span>
                      {selectedProject.stage && (
                        <span className="stage-badge">📍 {selectedProject.stage}</span>
                      )}
                      <button
                        onClick={() => navigator.clipboard.writeText(selectedProject.adapted_prompt!)}
                        className="secondary-button-small"
                      >
                        📋 Copy
                      </button>
                    </div>
                  </section>

                  <section className="detail-section">
                    <div className="section-header">
                      <h3>{user?.username === 'admin' ? 'Adapted Prompt' : '📋 책 집필 계획'}</h3>
                      <div className="section-actions">
                        <button
                          onClick={() => setIsPlanCollapsed(!isPlanCollapsed)}
                          className="secondary-button-small"
                        >
                          {isPlanCollapsed ? '▼ 펼치기' : '▲ 접기'}
                        </button>
                      </div>
                    </div>
                    {!isPlanCollapsed && (
                      <textarea
                        className="output-textarea"
                        value={selectedProject.adapted_prompt}
                        readOnly
                        rows={25}
                      />
                    )}
                  </section>

                  {/* User Feedback Section for Stage 1 */}
                  {selectedProject.stage === '1단계' && selectedProject.stage_status !== 'in_progress' && (
                    <>
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>💬 Your Feedback on the Plan (Optional)</h3>
                        </div>
                        <p className="feedback-hint">
                          Do you have any specific requirements or suggestions for the book content?
                          For example: "Chapter 3 should include a comprehensive historical review" or
                          "Focus more on practical examples in all chapters"
                        </p>
                        <textarea
                          className="feedback-textarea"
                          value={userFeedback}
                          onChange={(e) => setUserFeedback(e.target.value)}
                          placeholder="Enter your feedback or suggestions here... (optional)"
                          rows={5}
                          disabled={feedbackSaved}
                        />
                        {!feedbackSaved && userFeedback && (
                          <button
                            onClick={() => handleSaveFeedback(selectedProject.id)}
                            className="secondary-button"
                            disabled={loading}
                            style={{ marginTop: '10px' }}
                          >
                            {loading ? '💾 Saving...' : '💾 Save Feedback'}
                          </button>
                        )}
                        {feedbackSaved && (
                          <div className="feedback-saved-message">
                            ✅ Feedback saved! You can now proceed to the next stage.
                          </div>
                        )}
                      </section>

                      {/* Proceed Button for Stage 1 */}
                      <section className="detail-section">
                        <div className="proceed-section">
                          <h3>📍 Current Stage: 1단계 (Plan Ready)</h3>
                          <p>
                            Your book plan is ready.
                            {userFeedback && !feedbackSaved ? ' Save your feedback first, then ' : ' '}
                            Click the button below to start writing the book in English with web research.
                          </p>
                          <button
                            onClick={() => handleUserProceedStage(selectedProject.id)}
                            className="primary-button"
                            disabled={loading}
                          >
                            {loading ? '⏳ Starting...' : '▶️ Proceed to Stage 2 (Write Book with Research)'}
                          </button>
                        </div>
                      </section>
                    </>
                  )}

                  {/* Show Logs Section (for Stage 2 onwards) */}
                  {(selectedProject.stage === '2단계' || selectedProject.stage_status === 'in_progress' || selectedProject.stage_status === 'completed') && (
                    <section className="detail-section">
                      <div className="section-header">
                        <h3>📊 Progress Logs</h3>
                        <button
                          onClick={toggleUserLogs}
                          className="secondary-button-small"
                        >
                          {showUserLogs ? '▲ Hide Logs' : '▼ Show Logs'}
                        </button>
                      </div>
                      {showUserLogs && (
                        <div className="user-logs-container">
                          <div className="log-container">
                            {userProjectLogs.length > 0 ? (
                              userProjectLogs.map((log) => (
                                <div key={log.id} className={`log-entry log-${log.level}`}>
                                  <span className="log-timestamp">
                                    {new Date(log.created_at).toLocaleTimeString()}
                                  </span>
                                  <span className="log-message">{log.message}</span>
                                </div>
                              ))
                            ) : (
                              <div className="log-entry log-info">
                                <span className="log-message">No logs yet...</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </section>
                  )}

                  {/* English Writing Results Section */}
                  {selectedProject.stage_status === 'completed' && contentInfo && (
                    <section className="detail-section">
                      <h3>📚 English Writing Results</h3>
                      <div className="content-info-grid">
                        <div className="info-card">
                          <div className="info-label">Folder Location</div>
                          <div className="info-value folder-path">{contentInfo.folder_location}</div>
                        </div>
                        <div className="info-card">
                          <div className="info-label">Total Chapters</div>
                          <div className="info-value">{contentInfo.total_chapters}</div>
                        </div>
                        <div className="info-card">
                          <div className="info-label">Total Words</div>
                          <div className="info-value">{contentInfo.total_words.toLocaleString()}</div>
                        </div>
                      </div>

                      <div className="chapters-list">
                        <h4>📄 Chapter Files</h4>
                        <div className="chapter-files-grid">
                          {contentInfo.chapters.map((chapter) => (
                            <div
                              key={chapter.chapter_number}
                              className="chapter-file-card"
                              onClick={() => openChapter(selectedProject.id, chapter.chapter_number)}
                            >
                              <div className="chapter-file-icon">📄</div>
                              <div className="chapter-file-info">
                                <div className="chapter-file-title">
                                  Chapter {chapter.chapter_number}: {chapter.title}
                                </div>
                                <div className="chapter-file-meta">
                                  {chapter.word_count.toLocaleString()} words
                                </div>
                              </div>
                              <div className="chapter-file-action">
                                View →
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </section>
                  )}

                  {/* Iterative Chatbox for Chapter Refinement - Stage 2 Completed */}
                  {selectedProject.stage === '2단계' && selectedProject.stage_status === 'completed' && (
                    <section className="detail-section">
                      <div className="section-header">
                        <h3>💬 Refine Chapters (Chat with AI Writer)</h3>
                      </div>
                      <p className="feedback-hint">
                        You can request the AI to rewrite specific chapters with more detail.
                        Example: "Write Chapter 3 with detail" or "Rewrite Chapter 5 with more examples"
                      </p>

                      {/* Chat History */}
                      {chatHistory.length > 0 && (
                        <div className="chat-history">
                          {chatHistory.map((msg, idx) => (
                            <div key={idx} className={`chat-message chat-${msg.role}`}>
                              <div className="chat-role">{msg.role === 'user' ? '👤 You' : '🤖 AI Writer'}</div>
                              <div className="chat-content">{msg.content}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Chat Input */}
                      <div className="chat-input-container">
                        <textarea
                          className="chat-input"
                          value={chatPrompt}
                          onChange={(e) => setChatPrompt(e.target.value)}
                          placeholder="E.g., 'Write Chapter 3 with detail' or 'Rewrite Chapter 5 with more clinical examples'"
                          rows={3}
                          disabled={chatLoading}
                        />
                        <button
                          onClick={() => handleRefineChapter(selectedProject.id)}
                          className="primary-button"
                          disabled={chatLoading || !chatPrompt.trim()}
                          style={{ marginTop: '10px' }}
                        >
                          {chatLoading ? '⏳ Processing...' : '✍️ Refine Chapter'}
                        </button>
                      </div>

                      {/* Proceed to Stage 3 Button */}
                      <div className="proceed-section" style={{ marginTop: '20px' }}>
                        <h3>📍 Ready for Next Stage?</h3>
                        <p>
                          When you're satisfied with the English writing, proceed to Stage 3 for fact-checking and critical review.
                        </p>
                        <button
                          onClick={() => handleUserProceedStage(selectedProject.id)}
                          className="primary-button"
                          disabled={loading}
                        >
                          {loading ? '⏳ Starting...' : '▶️ Proceed to Stage 3 (Fact Check & Review)'}
                        </button>
                      </div>
                    </section>
                  )}

                  {/* Stage 3 - Fact Check & Critical Review Section */}
                  {selectedProject.stage === '3단계' && selectedProject.stage_status === 'completed' && (
                    <>
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>📋 Fact-Check & Critical Review Report</h3>
                        </div>
                        {selectedProject.user_feedback && selectedProject.user_feedback.includes('Stage 3:') ? (
                          <div className="review-report-container" style={{
                            backgroundColor: '#f8f9fa',
                            border: '1px solid #dee2e6',
                            borderRadius: '8px',
                            padding: '20px',
                            maxHeight: '600px',
                            overflowY: 'auto'
                          }}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {selectedProject.user_feedback.split('## Stage 3:')[1] || selectedProject.user_feedback}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <div className="info-message">
                            No review report found. Check Progress Logs for details.
                          </div>
                        )}
                      </section>

                      {/* Revision Chatbox at Stage 3 */}
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>✏️ Make Revisions Based on Review</h3>
                        </div>
                        <p className="feedback-hint">
                          Use the review report above to improve your book.
                          Example: "Revise Chapter 2 to include more specific examples as suggested in the review"
                        </p>

                        {/* Chat History */}
                        {chatHistory.length > 0 && (
                          <div className="chat-history">
                            {chatHistory.map((msg, idx) => (
                              <div key={idx} className={`chat-message chat-${msg.role}`}>
                                <div className="chat-role">{msg.role === 'user' ? '👤 You' : '🤖 AI Writer'}</div>
                                <div className="chat-content">{msg.content}</div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Chat Input */}
                        <div className="chat-input-container">
                          <textarea
                            className="chat-input"
                            value={chatPrompt}
                            onChange={(e) => setChatPrompt(e.target.value)}
                            placeholder="E.g., 'Revise Chapter 3 to add specific examples' or 'Improve Chapter 1 based on review feedback'"
                            rows={3}
                            disabled={chatLoading}
                          />
                          <button
                            onClick={() => handleRefineChapter(selectedProject.id)}
                            className="primary-button"
                            disabled={chatLoading || !chatPrompt.trim()}
                            style={{ marginTop: '10px' }}
                          >
                            {chatLoading ? '⏳ Processing...' : '✍️ Revise Chapter'}
                          </button>
                        </div>

                        {/* Proceed to Stage 4 Button */}
                        <div className="proceed-section" style={{ marginTop: '20px' }}>
                          <h3>📍 Ready to Finalize?</h3>
                          <p>
                            When you're satisfied with all revisions, proceed to Stage 4 for final polish and translation.
                          </p>
                          <button
                            onClick={() => handleUserProceedStage(selectedProject.id)}
                            className="primary-button"
                            disabled={loading}
                          >
                            {loading ? '⏳ Starting...' : '▶️ Proceed to Stage 4 (Final Polish)'}
                          </button>
                        </div>
                      </section>
                    </>
                  )}

                  {/* Stage 3 In Progress */}
                  {selectedProject.stage === '3단계' && selectedProject.stage_status === 'in_progress' && (
                    <section className="detail-section">
                      <div className="info-message">
                        ⏳ Fact-checking and critical review in progress... Check Progress Logs for updates.
                      </div>
                    </section>
                  )}

                  {/* Stage 4 - Final Completion with ALL Artifacts */}
                  {selectedProject.stage === '4단계' && (
                    <>
                      {/* Stage 4 In Progress - PDF Generation */}
                      {selectedProject.stage_status === 'in_progress' && (
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>📄 Generating PDF...</h3>
                          </div>
                          <div className="info-message" style={{ padding: '20px', backgroundColor: '#fff3cd', border: '1px solid #ffeaa7', borderRadius: '5px' }}>
                            <p>⏳ Your book PDF is being generated. This may take a minute...</p>
                            <p>Check the Progress Logs below for updates.</p>
                          </div>
                        </section>
                      )}

                      {/* Stage 4 Completion Banner */}
                      {selectedProject.stage_status === 'completed' && (
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>🎉 Book Creation Complete!</h3>
                        </div>
                        <div className="success-message" style={{ padding: '20px', backgroundColor: '#d4edda', border: '1px solid #c3e6cb', borderRadius: '5px' }}>
                          <h4>✅ Your book is ready!</h4>
                          <p>Congratulations! You've completed all stages of the book creation process.</p>
                          <p><strong>All artifacts from each stage are preserved below:</strong></p>
                          <ul>
                            <li>✅ Stage 1: Plan generation with your feedback</li>
                            <li>✅ Stage 2: English writing with web research</li>
                            <li>✅ Stage 3: Fact-checking and critical review</li>
                            <li>✅ Stage 4: PDF generated and ready for download</li>
                          </ul>
                        </div>

                        {/* PDF Download Section */}
                        {pdfStatus?.has_pdf && (
                          <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#e8f4fd', border: '1px solid #bee5eb', borderRadius: '8px' }}>
                            <h4 style={{ margin: '0 0 10px 0', color: '#0c5460' }}>📥 Download Your Book (English)</h4>
                            <p style={{ margin: '0 0 15px 0', color: '#0c5460' }}>
                              Your files are ready! PDF size: {pdfStatus.pdf_size ? `${(pdfStatus.pdf_size / 1024).toFixed(0)} KB` : 'Unknown'}
                            </p>
                            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                              <button
                                onClick={() => handleDownloadPdf(selectedProject.id)}
                                className="primary-button"
                                disabled={pdfLoading}
                                style={{ fontSize: '14px', padding: '10px 20px' }}
                              >
                                {pdfLoading ? '⏳ Preparing...' : '📄 Download PDF'}
                              </button>
                              <button
                                onClick={() => handleDownloadMarkdown(selectedProject.id)}
                                className="secondary-button"
                                style={{ fontSize: '14px', padding: '10px 20px' }}
                              >
                                📝 Download Markdown
                              </button>
                            </div>
                          </div>
                        )}

                        {/* PDF Not Available Yet */}
                        {pdfStatus && !pdfStatus.has_pdf && (
                          <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fff3cd', border: '1px solid #ffeaa7', borderRadius: '8px' }}>
                            <p style={{ margin: 0, color: '#856404' }}>
                              ⚠️ PDF not found. The PDF may still be generating or there was an error.
                              Check the Progress Logs for details.
                            </p>
                          </div>
                        )}
                      </section>
                      )}

                      {/* Stage 1 Artifacts - Initial Feedback */}
                      {selectedProject.user_feedback && !selectedProject.user_feedback.includes('## Stage 3:') && (
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>📝 Stage 1: Your Initial Feedback</h3>
                          </div>
                          <div style={{ backgroundColor: '#f8f9fa', padding: '15px', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                            <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{selectedProject.user_feedback.split('## Stage 3:')[0]}</p>
                          </div>
                        </section>
                      )}

                      {/* Stage 2 Artifacts - English Writing Results */}
                      {contentInfo && (
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>📚 Stage 2: English Writing Results</h3>
                          </div>
                          <div className="content-info-grid">
                            <div className="info-card">
                              <div className="info-label">Folder Location</div>
                              <div className="info-value folder-path">{contentInfo.folder_location}</div>
                            </div>
                            <div className="info-card">
                              <div className="info-label">Total Chapters</div>
                              <div className="info-value">{contentInfo.total_chapters}</div>
                            </div>
                            <div className="info-card">
                              <div className="info-label">Total Words</div>
                              <div className="info-value">{contentInfo.total_words.toLocaleString()}</div>
                            </div>
                          </div>

                          <div className="chapters-list">
                            <h4>📄 Chapter Files</h4>
                            <div className="chapter-files-grid">
                              {contentInfo.chapters.map((chapter) => (
                                <div
                                  key={chapter.chapter_number}
                                  className="chapter-file-card"
                                  onClick={() => openChapter(selectedProject.id, chapter.chapter_number)}
                                >
                                  <div className="chapter-file-icon">📄</div>
                                  <div className="chapter-file-info">
                                    <div className="chapter-file-title">
                                      Chapter {chapter.chapter_number}: {chapter.title}
                                    </div>
                                    <div className="chapter-file-meta">
                                      {chapter.word_count.toLocaleString()} words
                                    </div>
                                  </div>
                                  <div className="chapter-file-action">
                                    View →
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </section>
                      )}

                      {/* Stage 2 Refinement History */}
                      {selectedProject.conversation_history && JSON.parse(selectedProject.conversation_history).length > 0 && (
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>💬 Stage 2: Refinement History</h3>
                          </div>
                          <div className="chat-history">
                            {JSON.parse(selectedProject.conversation_history).map((msg: any, idx: number) => (
                              <div key={idx} className={`chat-message chat-${msg.role}`}>
                                <div className="chat-role">{msg.role === 'user' ? '👤 You' : '🤖 AI Writer'}</div>
                                <div className="chat-content">{msg.content}</div>
                              </div>
                            ))}
                          </div>
                        </section>
                      )}

                      {/* Stage 3 Artifacts - Fact-Check Report */}
                      {selectedProject.user_feedback && selectedProject.user_feedback.includes('## Stage 3:') && (
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>📋 Stage 3: Fact-Check & Critical Review Report</h3>
                          </div>
                          <div className="review-report-container" style={{
                            backgroundColor: '#f8f9fa',
                            border: '1px solid #dee2e6',
                            borderRadius: '8px',
                            padding: '20px',
                            maxHeight: '600px',
                            overflowY: 'auto'
                          }}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {selectedProject.user_feedback.split('## Stage 3:')[1] || selectedProject.user_feedback}
                            </ReactMarkdown>
                          </div>
                        </section>
                      )}

                      {/* Progress Logs - All Stages */}
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>📜 Complete Progress Logs</h3>
                          <button
                            onClick={toggleUserLogs}
                            className="secondary-button-small"
                          >
                            {showUserLogs ? '▲ Hide Logs' : '▼ Show Logs'}
                          </button>
                        </div>
                        {showUserLogs && (
                          <div className="user-logs-container">
                            <div className="log-container">
                              {userProjectLogs.length > 0 ? (
                                userProjectLogs.map((log) => (
                                  <div key={log.id} className={`log-entry log-${log.level}`}>
                                    <span className="log-timestamp">
                                      {new Date(log.created_at).toLocaleTimeString()}
                                    </span>
                                    <span className="log-message">{log.message}</span>
                                  </div>
                                ))
                              ) : (
                                <div className="log-entry log-info">
                                  <span className="log-message">No logs yet...</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </section>

                      {/* Proceed to Korean Translation */}
                      {selectedProject.stage_status === 'completed' && (
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>🌐 Want a Korean Version?</h3>
                        </div>
                        <div style={{ padding: '20px', backgroundColor: '#e3f2fd', border: '1px solid #90caf9', borderRadius: '8px' }}>
                          <p style={{ marginBottom: '15px' }}>
                            Your English PDF is ready! Would you like to translate your book to Korean?
                          </p>
                          <button
                            onClick={() => handleUserProceedStage(selectedProject.id)}
                            className="primary-button"
                            disabled={loading}
                            style={{ fontSize: '16px', padding: '12px 24px' }}
                          >
                            {loading ? '⏳ Starting...' : '🇰🇷 Proceed to Stage 5 (Korean Translation)'}
                          </button>
                        </div>
                      </section>
                      )}
                    </>
                  )}

                  {/* Stage 5 - Korean Translation */}
                  {selectedProject.stage === '5단계' && (
                    <>
                      {/* Stage 5 In Progress */}
                      {selectedProject.stage_status === 'in_progress' && (
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>🌐 Translating to Korean...</h3>
                          </div>
                          <div className="info-message" style={{ padding: '20px', backgroundColor: '#fff3cd', border: '1px solid #ffeaa7', borderRadius: '5px' }}>
                            <p>⏳ Your book is being translated to Korean. This may take several minutes...</p>
                            <p>Each chapter will be translated individually for best quality.</p>
                            <p>Check the Progress Logs below for updates.</p>
                          </div>
                        </section>
                      )}

                      {/* Stage 5 Completed */}
                      {selectedProject.stage_status === 'completed' && (
                        <>
                        <section className="detail-section">
                          <div className="section-header">
                            <h3>🎉 Korean Translation Complete!</h3>
                          </div>
                          <div className="success-message" style={{ padding: '20px', backgroundColor: '#d4edda', border: '1px solid #c3e6cb', borderRadius: '5px' }}>
                            <h4>✅ Your book is now available in both English and Korean!</h4>
                            <p>All stages have been completed successfully.</p>
                            <ul>
                              <li>✅ Stage 1: Plan generation</li>
                              <li>✅ Stage 2: English writing</li>
                              <li>✅ Stage 3: Fact-checking and review</li>
                              <li>✅ Stage 4: English PDF generated</li>
                              <li>✅ Stage 5: Korean translation and PDF generated</li>
                            </ul>
                          </div>

                          {/* Download Buttons */}
                          <div style={{ marginTop: '20px', display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                            {/* English Downloads */}
                            {pdfStatus?.has_pdf && (
                              <div style={{ flex: '1', minWidth: '280px', padding: '20px', backgroundColor: '#e8f4fd', border: '1px solid #bee5eb', borderRadius: '8px' }}>
                                <h4 style={{ margin: '0 0 10px 0', color: '#0c5460' }}>📥 English Version</h4>
                                <p style={{ margin: '0 0 15px 0', color: '#0c5460', fontSize: '14px' }}>
                                  PDF: {pdfStatus.pdf_size ? `${(pdfStatus.pdf_size / 1024).toFixed(0)} KB` : 'Unknown'}
                                </p>
                                <div style={{ display: 'flex', gap: '8px', flexDirection: 'column' }}>
                                  <button
                                    onClick={() => handleDownloadPdf(selectedProject.id)}
                                    className="secondary-button"
                                    disabled={pdfLoading}
                                    style={{ width: '100%' }}
                                  >
                                    {pdfLoading ? '⏳ Preparing...' : '📄 Download PDF'}
                                  </button>
                                  <button
                                    onClick={() => handleDownloadMarkdown(selectedProject.id)}
                                    className="secondary-button-small"
                                    style={{ width: '100%', padding: '8px' }}
                                  >
                                    📝 Download Markdown
                                  </button>
                                </div>
                              </div>
                            )}

                            {/* Korean Downloads */}
                            {pdfStatus?.has_korean_pdf && (
                              <div style={{ flex: '1', minWidth: '280px', padding: '20px', backgroundColor: '#fff3e0', border: '1px solid #ffcc80', borderRadius: '8px' }}>
                                <h4 style={{ margin: '0 0 10px 0', color: '#e65100' }}>📥 한글 버전</h4>
                                <p style={{ margin: '0 0 15px 0', color: '#e65100', fontSize: '14px' }}>
                                  PDF: {pdfStatus.korean_pdf_size ? `${(pdfStatus.korean_pdf_size / 1024).toFixed(0)} KB` : '알 수 없음'}
                                </p>
                                <div style={{ display: 'flex', gap: '8px', flexDirection: 'column' }}>
                                  <button
                                    onClick={() => handleDownloadKoreanPdf(selectedProject.id)}
                                    className="primary-button"
                                    disabled={pdfLoading}
                                    style={{ width: '100%' }}
                                  >
                                    {pdfLoading ? '⏳ 준비 중...' : '📄 PDF 다운로드'}
                                  </button>
                                  <button
                                    onClick={() => handleDownloadKoreanMarkdown(selectedProject.id)}
                                    className="secondary-button-small"
                                    style={{ width: '100%', padding: '8px' }}
                                  >
                                    📝 마크다운 다운로드
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        </section>

                        {/* Chapter Files - Stage 5 */}
                        {contentInfo && (
                          <section className="detail-section">
                            <div className="section-header">
                              <h3>📚 Book Chapters (English)</h3>
                            </div>
                            <div className="content-info-grid">
                              <div className="info-card">
                                <div className="info-label">Total Chapters</div>
                                <div className="info-value">{contentInfo.total_chapters}</div>
                              </div>
                              <div className="info-card">
                                <div className="info-label">Total Words</div>
                                <div className="info-value">{contentInfo.total_words.toLocaleString()}</div>
                              </div>
                            </div>

                            <div className="chapters-list">
                              <h4>📄 View Individual Chapters</h4>
                              <div className="chapter-files-grid">
                                {contentInfo.chapters.map((chapter) => (
                                  <div
                                    key={chapter.chapter_number}
                                    className="chapter-file-card"
                                    onClick={() => openChapter(selectedProject.id, chapter.chapter_number)}
                                  >
                                    <div className="chapter-file-icon">📄</div>
                                    <div className="chapter-file-info">
                                      <div className="chapter-file-title">
                                        Chapter {chapter.chapter_number}: {chapter.title}
                                      </div>
                                      <div className="chapter-file-meta">
                                        {chapter.word_count.toLocaleString()} words
                                      </div>
                                    </div>
                                    <div className="chapter-file-action">
                                      View →
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </section>
                        )}
                        </>
                      )}

                      {/* Progress Logs for Stage 5 */}
                      <section className="detail-section">
                        <div className="section-header">
                          <h3>📊 Progress Logs</h3>
                          <button
                            onClick={toggleUserLogs}
                            className="secondary-button-small"
                          >
                            {showUserLogs ? '▲ Hide Logs' : '▼ Show Logs'}
                          </button>
                        </div>
                        {showUserLogs && (
                          <div className="user-logs-container">
                            <div className="log-container">
                              {userProjectLogs.length > 0 ? (
                                userProjectLogs.map((log) => (
                                  <div key={log.id} className={`log-entry log-${log.level}`}>
                                    <span className="log-timestamp">
                                      {new Date(log.created_at).toLocaleTimeString()}
                                    </span>
                                    <span className="log-message">{log.message}</span>
                                  </div>
                                ))
                              ) : (
                                <div className="log-entry log-info">
                                  <span className="log-message">No logs yet...</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </section>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {/* Admin Dashboard View */}
        {view === 'admin' && user?.username === 'admin' && (
          <div className="admin-view">
            <div className="view-header">
              <h2>Admin Dashboard</h2>
              <div className="header-actions">
                <button onClick={() => setView('terminal')} className="secondary-button-small">
                  💻 Terminal
                </button>
                <button onClick={() => setView('list')} className="secondary-button">
                  ← Back to My Projects
                </button>
              </div>
            </div>

            {/* Stats Cards */}
            {adminStats && (
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-value">{adminStats.total_users}</div>
                  <div className="stat-label">Total Users</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{adminStats.total_projects}</div>
                  <div className="stat-label">Total Projects</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{adminStats.total_prompts_generated}</div>
                  <div className="stat-label">Prompts Generated</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{(adminStats.total_tokens_used || 0).toLocaleString()}</div>
                  <div className="stat-label">Total Tokens</div>
                </div>
              </div>
            )}

            {/* Users Section */}
            <section className="admin-section">
              <h3>All Users</h3>
              <div className="admin-table">
                <table>
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Created</th>
                      <th>Projects</th>
                      <th>Tokens Used</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allUsers && allUsers.map(user => (
                      <tr key={user.id}>
                        <td><strong>{user.username}</strong></td>
                        <td>{new Date(user.created_at).toLocaleDateString()}</td>
                        <td>{user.project_count}</td>
                        <td>{(user.total_tokens || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* All Projects Section */}
            <section className="admin-section">
              <h3>All Projects</h3>
              <div className="admin-table">
                <table>
                  <thead>
                    <tr>
                      <th>Project Name</th>
                      <th>Owner</th>
                      <th>Status</th>
                      <th>Stage</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allProjects && allProjects.map(project => (
                      <>
                        <tr key={project.id}>
                          <td><strong>{project.name}</strong></td>
                          <td>{project.owner_username}</td>
                          <td>
                            {project.stage_status === 'completed' ? (
                              <span className="status-badge success">✅ English writing finished</span>
                            ) : project.stage_status === 'in_progress' ? (
                              <span className="status-badge warning">⏳ Writing in progress...</span>
                            ) : project.adapted_prompt ? (
                              <span className="status-badge success">Generated</span>
                            ) : (
                              <span className="status-badge pending">Not generated</span>
                            )}
                          </td>
                          <td>
                            {project.stage ? (
                              <span className="stage-badge-table">{project.stage}</span>
                            ) : (
                              <span className="stage-badge-empty">-</span>
                            )}
                          </td>
                          <td>{new Date(project.created_at).toLocaleDateString()}</td>
                          <td>
                            <div className="action-buttons">
                              {project.stage === '1단계' && project.stage_status !== 'in_progress' && (
                                <button
                                  onClick={() => handleProceedStage(project.id)}
                                  className="primary-button-small"
                                  disabled={loading}
                                >
                                  ▶️ Proceed
                                </button>
                              )}
                              {(project.stage === '2단계' || project.stage_status === 'in_progress' || project.stage_status === 'completed') && (
                                <button
                                  onClick={() => toggleLogExpansion(project.id)}
                                  className="secondary-button-small"
                                >
                                  {expandedLogRows.has(project.id) ? '▲ Hide Logs' : '▼ Show Logs'}
                                </button>
                              )}
                              <button
                                onClick={() => setEditingProject(project)}
                                className="secondary-button-small"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleAdminDeleteProject(project.id)}
                                className="danger-button-small"
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                        {expandedLogRows.has(project.id) && (
                          <tr key={`${project.id}-logs`} className="log-row">
                            <td colSpan={6}>
                              <div className="project-logs">
                                <h4>📋 Server Log - {project.name}</h4>
                                <div className="log-container">
                                  {projectLogs.get(project.id)?.length ? (
                                    projectLogs.get(project.id)!.map((log) => (
                                      <div key={log.id} className={`log-entry log-${log.level}`}>
                                        <span className="log-timestamp">
                                          {new Date(log.created_at).toLocaleTimeString()}
                                        </span>
                                        <span className="log-message">{log.message}</span>
                                      </div>
                                    ))
                                  ) : (
                                    <div className="log-entry log-info">
                                      <span className="log-message">No logs yet...</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Recent Activity */}
            {adminStats && adminStats.recent_projects && adminStats.recent_projects.length > 0 && (
              <section className="admin-section">
                <h3>Recent Activity</h3>
                <div className="recent-activity">
                  {adminStats.recent_projects.map(project => (
                    <div key={project.id} className="activity-item">
                      <div className="activity-header">
                        <strong>{project.owner_username}</strong> created <strong>{project.name}</strong>
                      </div>
                      <div className="activity-meta">
                        {new Date(project.created_at).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Generated Books */}
            <section className="admin-section">
              <h3>Generated Books</h3>
              {bookGroups.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)' }}>No generated books found.</p>
              ) : (
                <div className="books-list">
                  {bookGroups.map((group, idx) => (
                    <div key={idx} className="book-group">
                      <div className="book-group-header">
                        <h4>{group.project_name}</h4>
                        <span className="book-count">{group.books.length} book{group.books.length > 1 ? 's' : ''}</span>
                      </div>
                      <div className="book-files">
                        {group.books.map((book, bookIdx) => (
                          <div key={bookIdx} className="book-item" onClick={() => openBook(book.path)}>
                            <div className="book-icon">📄</div>
                            <div className="book-info">
                              <div className="book-filename">{book.filename}</div>
                              <div className="book-meta">
                                {(book.size / 1024 / 1024).toFixed(2)} MB • Modified: {new Date(book.modified).toLocaleDateString()}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* Terminal View */}
        {view === 'terminal' && user?.username === 'admin' && (
          <div className="terminal-view">
            <div className="view-header">
              <h2>Server Terminal</h2>
              <button onClick={() => setView('admin')} className="secondary-button">
                ← Back to Dashboard
              </button>
            </div>

            <div className="terminal-container">
              <div className="terminal-info">
                <span>🔒 Restricted to: /var/www/aibook</span>
                <span>Press Ctrl+C to interrupt | Ctrl+D to exit</span>
              </div>
              <div id="terminal" className="terminal-wrapper"></div>
            </div>
          </div>
        )}

        {/* Workflow View */}
        {view === 'workflow' && (
          <div className="workflow-view">
            <div className="view-header">
              <h2>📋 출판절차</h2>
              <button onClick={() => setView('list')} className="secondary-button">
                ← 내 프로젝트로
              </button>
            </div>

            <div className="workflow-container">
              <svg viewBox="0 0 800 1800" xmlns="http://www.w3.org/2000/svg" className="workflow-svg">
                <defs>
                  <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                    <polygon points="0 0, 10 3, 0 6" fill="#3b82f6" />
                  </marker>
                  <filter id="shadow">
                    <feDropShadow dx="2" dy="2" stdDeviation="3" floodOpacity="0.3"/>
                  </filter>
                </defs>

                {/* Step 1 */}
                <rect x="150" y="20" width="500" height="120" rx="10" fill="#3b82f6" filter="url(#shadow)"/>
                <text x="400" y="50" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">1단계</text>
                <text x="400" y="75" textAnchor="middle" fill="white" fontSize="16">회원가입, 로그인, 프로젝트생성</text>
                <text x="400" y="100" textAnchor="middle" fill="white" fontSize="16">책내용 작성, 생성 버튼 누르기</text>
                <text x="400" y="125" textAnchor="middle" fill="white" fontSize="14">👤 고객 작업</text>

                <line x1="400" y1="140" x2="400" y2="180" stroke="#3b82f6" strokeWidth="3" markerEnd="url(#arrowhead)"/>

                {/* Step 2 */}
                <rect x="150" y="180" width="500" height="140" rx="10" fill="#10b981" filter="url(#shadow)"/>
                <text x="400" y="210" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">2단계</text>
                <text x="400" y="235" textAnchor="middle" fill="white" fontSize="16">출판사 AI 서버 작업개시</text>
                <text x="400" y="260" textAnchor="middle" fill="white" fontSize="16">목차 생성, 목차 요약</text>
                <text x="400" y="285" textAnchor="middle" fill="white" fontSize="14">🤖 AI 작업</text>
                <text x="400" y="310" textAnchor="middle" fill="#fef3c7" fontSize="16" fontWeight="bold">→ 사용자 승인 요청 → 대기</text>

                <line x1="400" y1="320" x2="400" y2="360" stroke="#10b981" strokeWidth="3" markerEnd="url(#arrowhead)"/>

                {/* Step 3 */}
                <rect x="150" y="360" width="500" height="140" rx="10" fill="#10b981" filter="url(#shadow)"/>
                <text x="400" y="390" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">3단계</text>
                <text x="400" y="415" textAnchor="middle" fill="white" fontSize="16">고객 승인확인</text>
                <text x="400" y="440" textAnchor="middle" fill="white" fontSize="16">챕터별 글쓰기 시작, 글쓰기 완성</text>
                <text x="400" y="465" textAnchor="middle" fill="white" fontSize="14">🤖 AI 작업</text>
                <text x="400" y="490" textAnchor="middle" fill="#fef3c7" fontSize="16" fontWeight="bold">→ 사용자 승인 요청 → 대기</text>

                <line x1="400" y1="500" x2="400" y2="540" stroke="#10b981" strokeWidth="3" markerEnd="url(#arrowhead)"/>

                {/* Step 4 */}
                <rect x="150" y="540" width="500" height="140" rx="10" fill="#10b981" filter="url(#shadow)"/>
                <text x="400" y="570" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">4단계</text>
                <text x="400" y="595" textAnchor="middle" fill="white" fontSize="16">고객 승인확인</text>
                <text x="400" y="620" textAnchor="middle" fill="white" fontSize="16">팩트체크, 비판적검토, 글내용 수정</text>
                <text x="400" y="645" textAnchor="middle" fill="white" fontSize="14">🤖 AI 작업</text>
                <text x="400" y="670" textAnchor="middle" fill="#fef3c7" fontSize="16" fontWeight="bold">→ 사용자 승인 요청 → 대기</text>

                <line x1="400" y1="680" x2="400" y2="720" stroke="#10b981" strokeWidth="3" markerEnd="url(#arrowhead)"/>

                {/* Step 5 */}
                <rect x="150" y="720" width="500" height="160" rx="10" fill="#10b981" filter="url(#shadow)"/>
                <text x="400" y="750" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">5단계</text>
                <text x="400" y="775" textAnchor="middle" fill="white" fontSize="16">고객 승인확인</text>
                <text x="400" y="800" textAnchor="middle" fill="white" fontSize="16">삽화삽입 계획, 삽화 이미지 생성</text>
                <text x="400" y="825" textAnchor="middle" fill="white" fontSize="16">영문판 PDF, DOCX 생성</text>
                <text x="400" y="850" textAnchor="middle" fill="white" fontSize="14">🤖 AI 작업</text>
                <text x="400" y="870" textAnchor="middle" fill="#fef3c7" fontSize="16" fontWeight="bold">→ 사용자 승인 요청 → 대기</text>

                <line x1="400" y1="880" x2="400" y2="920" stroke="#10b981" strokeWidth="3" markerEnd="url(#arrowhead)"/>

                {/* Step 6 */}
                <rect x="150" y="920" width="500" height="160" rx="10" fill="#10b981" filter="url(#shadow)"/>
                <text x="400" y="950" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">6단계</text>
                <text x="400" y="975" textAnchor="middle" fill="white" fontSize="16">고객 승인확인</text>
                <text x="400" y="1000" textAnchor="middle" fill="white" fontSize="16">번역계획 (말투, 문체, 대상독자)</text>
                <text x="400" y="1025" textAnchor="middle" fill="white" fontSize="16">번역시작, 한글 PDF, DOCX 생성</text>
                <text x="400" y="1050" textAnchor="middle" fill="white" fontSize="14">🤖 AI 작업</text>
                <text x="400" y="1070" textAnchor="middle" fill="#fef3c7" fontSize="16" fontWeight="bold">→ 사용자 승인 요청 → 대기</text>

                <line x1="400" y1="1080" x2="400" y2="1120" stroke="#10b981" strokeWidth="3" markerEnd="url(#arrowhead)"/>

                {/* Step 7 */}
                <rect x="150" y="1120" width="500" height="120" rx="10" fill="#f59e0b" filter="url(#shadow)"/>
                <text x="400" y="1150" textAnchor="middle" fill="white" fontSize="24" fontWeight="bold">7단계</text>
                <text x="400" y="1175" textAnchor="middle" fill="white" fontSize="16">고객 승인확인</text>
                <text x="400" y="1200" textAnchor="middle" fill="white" fontSize="16">PDF, DOCX 다운로드</text>
                <text x="400" y="1225" textAnchor="middle" fill="white" fontSize="14">✅ 완료</text>

                {/* Legend */}
                <text x="150" y="1280" fill="#3b82f6" fontSize="18" fontWeight="bold">범례:</text>
                <rect x="150" y="1290" width="30" height="30" rx="5" fill="#3b82f6"/>
                <text x="190" y="1310" fill="#1f2937" fontSize="16">고객 작업</text>

                <rect x="150" y="1330" width="30" height="30" rx="5" fill="#10b981"/>
                <text x="190" y="1350" fill="#1f2937" fontSize="16">AI 자동 작업</text>

                <rect x="150" y="1370" width="30" height="30" rx="5" fill="#f59e0b"/>
                <text x="190" y="1390" fill="#1f2937" fontSize="16">완료 단계</text>

                <rect x="400" y="1290" width="30" height="30" rx="5" fill="#fef3c7" stroke="#f59e0b" strokeWidth="2"/>
                <text x="440" y="1310" fill="#1f2937" fontSize="16">승인 대기</text>
              </svg>

              <div className="workflow-description">
                <h3>✨ 완전 자동화된 AI 출판 프로세스</h3>
                <p>
                  디지탈 아카이브 출판사는 최첨단 인공지능 기술을 활용하여
                  책 기획부터 출판까지 전 과정을 자동화합니다.
                </p>
                <ul>
                  <li>📝 <strong>자동 집필:</strong> AI가 목차부터 본문까지 전문적으로 작성</li>
                  <li>🔍 <strong>품질 관리:</strong> 팩트체크와 비판적 검토로 정확성 보장</li>
                  <li>🎨 <strong>삽화 생성:</strong> AI가 맞춤형 이미지 자동 생성</li>
                  <li>🌐 <strong>다국어 지원:</strong> 영문/한글 동시 출판</li>
                  <li>👥 <strong>고객 중심:</strong> 각 단계마다 승인 과정 포함</li>
                </ul>
                <p className="workflow-note">
                  💡 <strong>참고:</strong> 모든 단계는 고객님의 승인을 받은 후 진행됩니다.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Records View */}
        {view === 'records' && (
          <div className="records-view">
            <div className="view-header">
              <h2>🎙️ Voice Files</h2>
              <button onClick={() => setView('list')} className="secondary-button">
                ← 내 프로젝트로
              </button>
            </div>

            <div className="records-content">
              {/* Upload Section */}
              <div className="upload-section">
                <h3>Upload Voice Files</h3>
                <p className="upload-description">
                  Upload audio/video files (.wav, .mp4, .m4a, .mp3, .ogg, .webm)
                </p>
                <label className="upload-button">
                  {voiceFileUploading ? (
                    <span>Uploading...</span>
                  ) : (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                      </svg>
                      <span>Select Files to Upload</span>
                    </>
                  )}
                  <input
                    type="file"
                    multiple
                    accept=".wav,.mp4,.m4a,.mp3,.ogg,.webm,audio/*,video/mp4"
                    onChange={handleVoiceFileUpload}
                    disabled={voiceFileUploading}
                    style={{ display: 'none' }}
                  />
                </label>
              </div>

              {/* File List Section */}
              <div className="voice-files-section">
                <h3>Your Voice Files ({voiceFiles.length})</h3>
                {voiceFiles.length === 0 ? (
                  <div className="empty-state">
                    <p>No voice files uploaded yet.</p>
                  </div>
                ) : (
                  <div className="voice-files-list">
                    {voiceFiles.map((file) => (
                      <div key={file.filename} className="voice-file-item">
                        <div className="file-info">
                          <span className="file-icon">🎵</span>
                          <div className="file-details">
                            <span className="file-name">{file.filename}</span>
                            <span className="file-meta">
                              {formatFileSize(file.size)} • {new Date(file.modified).toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <div className="file-actions">
                          <audio
                            controls
                            className="audio-player"
                          >
                            <source src={`/api/voice-files/${encodeURIComponent(file.filename)}`} />
                            Your browser does not support audio playback.
                          </audio>
                          <button
                            onClick={() => handleDeleteVoiceFile(file.filename)}
                            className="delete-button"
                            title="Delete file"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Published Books View */}
        {view === 'published_books' && (
          <div className="published-books-view">
            <div className="view-header">
              <h2>📖 우리가 펴낸 책</h2>
              <button onClick={() => setView('list')} className="secondary-button">
                ← 내 프로젝트로
              </button>
            </div>

            <section className="books-section">
              {bookGroups.length === 0 ? (
                <div className="empty-state">
                  <p>아직 출판된 책이 없습니다.</p>
                </div>
              ) : (
                <div className="books-list">
                  {bookGroups.map((group, idx) => (
                    <div key={idx} className="book-group">
                      <div className="book-group-header">
                        <h4>{group.project_name}</h4>
                        <span className="book-count">{group.books.length}권</span>
                      </div>
                      <div className="book-files">
                        {group.books.map((book, bookIdx) => (
                          <div key={bookIdx} className="book-item" onClick={() => openBook(book.path)}>
                            <div className="book-icon">📄</div>
                            <div className="book-info">
                              <div className="book-filename">{book.filename}</div>
                              <div className="book-meta">
                                {(book.size / 1024 / 1024).toFixed(2)} MB • 수정: {new Date(book.modified).toLocaleDateString('ko-KR')}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* Edit Project Modal */}
        {editingProject && (
          <div className="modal-overlay" onClick={() => setEditingProject(null)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h3>Edit Project: {editingProject.name}</h3>
              <div className="form-group">
                <label>Project Name</label>
                <input
                  type="text"
                  value={editingProject.name}
                  onChange={(e) => setEditingProject({ ...editingProject, name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Book Idea</label>
                <textarea
                  value={editingProject.book_idea}
                  onChange={(e) => setEditingProject({ ...editingProject, book_idea: e.target.value })}
                  rows={5}
                />
              </div>
              {editingProject.adapted_prompt && (
                <div className="form-group">
                  <label>Adapted Prompt</label>
                  <textarea
                    value={editingProject.adapted_prompt}
                    onChange={(e) => setEditingProject({ ...editingProject, adapted_prompt: e.target.value })}
                    rows={10}
                  />
                </div>
              )}
              <div className="modal-actions">
                <button
                  onClick={() => handleAdminUpdateProject(editingProject.id, {
                    name: editingProject.name,
                    book_idea: editingProject.book_idea,
                    adapted_prompt: editingProject.adapted_prompt
                  })}
                  className="primary-button"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
                <button onClick={() => setEditingProject(null)} className="secondary-button">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <h3>디지탈 아카이브 출판사</h3>
          <p className="footer-credit">Powered by Groq API • v3.0</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
