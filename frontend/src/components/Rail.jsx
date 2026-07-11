import { MessageCircle, BookOpen, NotebookText } from 'lucide-react';
import { PersonaAvatar } from './Shared';
import { initial } from '../utils';

const NAV = [
  { key: 'chat', label: 'Chat', Icon: MessageCircle },
  { key: 'words', label: 'Words', Icon: BookOpen },
  { key: 'memory', label: 'Memory', Icon: NotebookText },
];

export default function Rail({ view, setView, personaName, userName }) {
  return (
    <div className="w-[68px] bg-[#FDFDFE] border-r border-border flex flex-col items-center pt-[18px] pb-4 gap-1.5 shrink-0">
      <div className="mb-[18px]">
        <PersonaAvatar name={personaName} size="sm" />
      </div>
      {NAV.map(({ key, label, Icon }) => (
        <button
          key={key}
          title={label}
          onClick={() => setView(key)}
          className={`w-11 h-11 rounded-[14px] border-none cursor-pointer flex items-center justify-center transition-all
            ${view === key ? 'bg-accent-soft text-accent' : 'bg-transparent text-muted hover:bg-[#F1F2F6]'}`}
        >
          <Icon size={19} strokeWidth={2} />
        </button>
      ))}
      <div className="flex-1" />
      <div
        title={userName}
        className="w-[34px] h-[34px] rounded-full bg-border-2 flex items-center justify-center text-[13px] font-semibold text-text-3"
      >
        {initial(userName)}
      </div>
    </div>
  );
}
