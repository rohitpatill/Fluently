import { MessageCircle, BookOpen, NotebookText, Settings } from 'lucide-react';
import { PersonaAvatar } from './Shared';
import { initial } from '../utils';

const NAV = [
  { key: 'chat', label: 'Chat', Icon: MessageCircle },
  { key: 'words', label: 'Words', Icon: BookOpen },
  { key: 'memory', label: 'Memory', Icon: NotebookText },
];

export default function Rail({ view, setView, personaName, personaAvatar = '', userName, me, hidden = false }) {
  return (
    <div className={`fixed inset-x-0 bottom-0 z-40 h-[76px] bg-[#FDFDFE]/95 border-t border-border items-center justify-around px-3 shadow-[0_-10px_28px_-24px_rgba(26,29,39,.35)] backdrop-blur md:static md:w-[68px] md:h-auto md:border-t-0 md:border-r md:flex-col md:justify-start md:pt-[18px] md:pb-4 md:gap-1.5 md:shadow-none md:backdrop-blur-none shrink-0 ${hidden ? 'hidden md:flex' : 'flex'}`}>
      <div className="hidden md:block md:mb-[18px]">
        <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="sm" />
      </div>
      {NAV.map(({ key, label, Icon }) => (
        <button
          key={key}
          title={label}
          onClick={() => setView(key)}
          className={`w-12 h-12 md:w-11 md:h-11 rounded-[14px] border-none cursor-pointer flex flex-col md:flex-row items-center justify-center gap-0.5 transition-all
            ${view === key ? 'bg-accent-soft text-accent' : 'bg-transparent text-muted hover:bg-[#F1F2F6]'}`}
        >
          <Icon size={19} strokeWidth={2} />
          <span className="text-[10px] leading-none md:hidden">{label}</span>
        </button>
      ))}
      <div className="hidden md:block md:flex-1" />
      <button
        title="Settings"
        onClick={() => setView('settings')}
        className={`w-12 h-12 md:w-11 md:h-11 rounded-[14px] border-none cursor-pointer flex flex-col md:flex-row items-center justify-center gap-0.5 transition-all md:mb-1.5
          ${view === 'settings' ? 'bg-accent-soft text-accent' : 'bg-transparent text-muted hover:bg-[#F1F2F6]'}`}
      >
        <Settings size={19} strokeWidth={2} />
        <span className="text-[10px] leading-none md:hidden">Settings</span>
      </button>
      <button
        title={`${userName || me?.name || 'You'} — open Settings`}
        onClick={() => setView('settings')}
        className="hidden md:flex w-[34px] h-[34px] rounded-full border-none p-0 cursor-pointer overflow-hidden bg-border-2 items-center justify-center text-[13px] font-semibold text-text-3"
      >
        {me?.picture ? (
          <img src={me.picture} alt="" referrerPolicy="no-referrer" className="w-full h-full object-cover" />
        ) : (
          initial(userName || me?.name)
        )}
      </button>
    </div>
  );
}
