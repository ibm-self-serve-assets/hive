import React, { useState } from 'react';
import { X, Server, Link2, Eye, EyeOff } from 'lucide-react';

interface ConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnect: (formData: any) => Promise<void>;
  initialServerUrl: string;
  initialProfileId: string;
}

export const ConnectionModal: React.FC<ConnectionModalProps> = ({
  isOpen,
  onClose,
  onConnect,
  initialServerUrl,
  initialProfileId,
}) => {
  const [serverUrl, setServerUrl] = useState(initialServerUrl || 'http://localhost:8080');
  const [token, setToken] = useState('password');
  const [showToken, setShowToken] = useState(false);
  const [profileId, setProfileId] = useState(initialProfileId || 'workshop-cluster');
  const [producerKey, setProducerKey] = useState('MOCK_KEY');
  const [producerSecret, setProducerSecret] = useState('MOCK_SECRET');
  const [showSecret, setShowSecret] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await onConnect({
        simulation_server_url: serverUrl,
        workshop_access_token: token,
        connection_profile_id: profileId,
        producer_api_key: producerKey,
        producer_api_secret: producerSecret,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Connection / provisioning failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white text-hive-navy rounded-xl max-w-md w-full p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 className="font-bold text-lg flex items-center space-x-2">
            <Server size={18} className="text-hive-blue" />
            <span>Connect to Simulation Server</span>
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-gray-700 mb-1">
              Simulation Server URL
            </label>
            <input
              type="text"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              required
              className="w-full px-3 py-2 border rounded border-gray-300 focus:outline-none focus:border-hive-blue font-mono"
              placeholder="http://localhost:8080"
            />
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">
              Workshop Access Token
            </label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
                className="w-full px-3 py-2 pr-10 border rounded border-gray-300 focus:outline-none focus:border-hive-blue font-mono"
                placeholder="password"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 focus:outline-none"
                aria-label={showToken ? 'Hide token' : 'Show token'}
              >
                {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="text-[10px] text-gray-400 mt-0.5">
              Default: password
            </p>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">
              Connection Profile ID
            </label>
            <input
              type="text"
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              required
              className="w-full px-3 py-2 border rounded border-gray-300 focus:outline-none focus:border-hive-blue font-mono"
              placeholder="workshop-cluster"
            />
          </div>

          <div className="grid grid-cols-2 gap-3 pt-1 border-t border-gray-100">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Producer Kafka Key
              </label>
              <input
                type="text"
                value={producerKey}
                onChange={(e) => setProducerKey(e.target.value)}
                required
                className="w-full px-3 py-2 border rounded border-gray-300 focus:outline-none focus:border-hive-blue font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Producer Secret
              </label>
              <div className="relative">
                <input
                  type={showSecret ? 'text' : 'password'}
                  value={producerSecret}
                  onChange={(e) => setProducerSecret(e.target.value)}
                  required
                  className="w-full px-3 py-2 pr-9 border rounded border-gray-300 focus:outline-none focus:border-hive-blue font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 focus:outline-none"
                  aria-label={showSecret ? 'Hide secret' : 'Show secret'}
                >
                  {showSecret ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded text-gray-600 hover:bg-gray-100 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-5 py-2 rounded font-semibold bg-hive-blue hover:bg-blue-600 text-white disabled:opacity-50 flex items-center space-x-1.5"
            >
              <Link2 size={14} />
              <span>{isLoading ? 'Connecting...' : 'Connect & Provision'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
