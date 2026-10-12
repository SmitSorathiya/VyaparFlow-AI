import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

export const workflowApi = {
  uploadImage: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/workflows', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  processWorkflow: async (id: number) => {
    const response = await api.post(`/workflows/${id}/process`, undefined, { timeout: 150000 });
    return response.data;
  },

  getWorkflow: async (id: number) => {
    const response = await api.get(`/workflows/${id}`);
    return response.data;
  },

  listWorkflows: async () => {
    const response = await api.get('/workflows');
    return response.data;
  },

  clarify: async (id: number, fields: any) => {
    const response = await api.post(`/workflows/${id}/clarify`, { fields });
    return response.data;
  },

  approve: async (id: number, action?: string, message?: string) => {
    const response = await api.post(`/workflows/${id}/approve`, { action, message });
    return response.data;
  },

  reject: async (id: number) => {
    const response = await api.post(`/workflows/${id}/reject`);
    return response.data;
  },

  getAuditLog: async (id: number) => {
    const response = await api.get(`/workflows/${id}/audit`);
    return response.data;
  },

  getDashboardStats: async () => {
    const response = await api.get('/dashboard-stats');
    return response.data;
  }
};
