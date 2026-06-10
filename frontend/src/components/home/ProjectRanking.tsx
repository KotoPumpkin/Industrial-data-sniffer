import CountUp from '../ui/CountUp';
import GlassPanel from '../ui/GlassPanel';
import { ProjectOverview } from '../../api/projects';
import { motion, AnimatePresence } from 'framer-motion';

interface ProjectRankingProps {
  projects: ProjectOverview[];
  type: 'production' | 'efficiency';
}

const NUM_COLORS = ['text-amber-300', 'text-gray-300', 'text-gray-400'];
const BG_COLORS = [
  'rgba(252,211,77,0.12)',
  'rgba(209,213,219,0.08)',
  'rgba(156,163,175,0.06)',
];

export default function ProjectRanking({ projects, type }: ProjectRankingProps) {
  const isProduction = type === 'production';
  const sorted = [...projects].sort((a, b) =>
    isProduction ? b.production_count - a.production_count : b.oee_avg - a.oee_avg
  );

  return (
    <GlassPanel className="p-4">
      <div className="text-[0.7rem] text-gray-400 uppercase tracking-[0.1em] mb-3.5 font-heading font-semibold">
        {isProduction ? '产量排行' : '效率排行'}
      </div>
      <div className="flex flex-col gap-3">
        <AnimatePresence>
          {sorted.map((p, i) => (
            <motion.div
              key={p.id}
              layout
              initial={{ opacity: 0, x: -24 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
              className="flex items-center gap-3"
            >
              <span
                className="w-6 h-6 rounded flex items-center justify-center text-[0.7rem] font-bold font-kpi"
                style={{ background: BG_COLORS[i] || BG_COLORS[2], color: i === 0 ? '#fcd34d' : '#d1d5db' }}
              >
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-[0.85rem] text-gray-300 font-body truncate">{p.name}</div>
                <div className="flex items-baseline gap-1.5">
                  <CountUp
                    end={isProduction ? p.production_count : p.oee_avg}
                    decimals={isProduction ? 0 : 1}
                    className={`text-xl font-bold font-kpi ${NUM_COLORS[i] || 'text-gray-400'}`}
                  />
                  <span className="text-[0.7rem] text-gray-500 font-data">
                    {isProduction ? '件' : '%'}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </GlassPanel>
  );
}
