import React, { useEffect, useState } from 'react';
import {
  Apple, Droplet, CheckCircle, Plus, Trash2, ShieldCheck,
  TrendingUp, AlertCircle, Utensils, Mic, Sparkles, CalendarCheck, Clock
} from 'lucide-react';
import { mealService, profileService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import NutritionVoiceAgentModal from '../components/nutrition/NutritionVoiceAgentModal';

export default function NutritionPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showMealForm, setShowMealForm] = useState(false);
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [mealInput, setMealInput] = useState({
    meal_type: 'LUNCH',
    food_description: '',
    portion: '1 plate',
    calories_optional: ''
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchMeals = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      const res = await mealService.getAll();
      setData(res.data);
    } catch (err) {
      console.error('Error fetching meals:', err);
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    fetchMeals();
  }, []);

  const handleAddMeal = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await mealService.log(mealInput);
      setMealInput({ meal_type: 'LUNCH', food_description: '', portion: '1 plate', calories_optional: '' });
      setShowMealForm(false);
      await fetchMeals();
    } catch (err) {
      console.error('Error logging meal:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteMeal = async (id) => {
    try {
      await mealService.delete(id);
      await fetchMeals(true);
    } catch (err) {
      console.error('Error deleting meal:', err);
    }
  };

  if (loading && !data) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Nutrition &amp; Metabolic Protocol from SQLite..." />
      </div>
    );
  }

  const meals = data?.meals || [];
  const profile = data?.profile || {};
  const scheduledPlanMeals = data?.scheduledPlanMeals || [];
  const hasMeals = meals.length > 0;
  const hasScheduledMeals = scheduledPlanMeals.length > 0;

  const todayStr = new Date().toISOString().substring(0, 10);
  const todayMeals = meals.filter(m => m.logged_at?.substring(0, 10) === todayStr);
  const mealCount = todayMeals.length;
  const adherencePct = Math.min(100, Math.round((mealCount / 3) * 100));

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>My Plan &gt; Nutrition &gt; Nutrition &amp; Healthy Eating</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Your Nutrition Plan</h1>
          <p className="text-sm text-emerald-100/70 mt-1.5 max-w-3xl">
            Practical nutrition guidance designed to support recovery, healthy energy levels, and daily hydration.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowVoiceModal(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-emerald-950/60 ring-1 ring-emerald-400/40 hover:scale-[1.02]"
          >
            <Mic size={16} className="text-emerald-200 animate-pulse" />
            <span>Talk to Nutrition Coach (AI Voice)</span>
          </button>

          <button
            onClick={() => setShowMealForm(!showMealForm)}
            className="flex items-center gap-2 bg-[#132213] hover:bg-emerald-900/40 text-emerald-200 border border-emerald-800/60 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
          >
            <Plus size={15} />
            <span>Manual Meal Log</span>
          </button>
        </div>
      </div>

      {/* AI Voice Nutrition Hero Banner */}
      <div className="bg-gradient-to-r from-[#0c1a0c] via-[#0f210f] to-[#0a150a] border border-emerald-500/40 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl ring-1 ring-emerald-500/20">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-300 shrink-0 shadow-inner">
            <Utensils size={24} className="animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">Interactive Voice Nutritionist &amp; Meal Planner</h2>
              <span className="text-[10px] bg-emerald-500/20 text-emerald-300 font-mono px-2 py-0.5 rounded-full border border-emerald-500/30">
                GPT-4o Mini (OpenRouter)
              </span>
            </div>
            <p className="text-xs text-emerald-100/75 mt-1 max-w-xl">
              Ask to prepare a full-day meal schedule tailored to your allergies, or speak what you ate to auto-log meals into SQLite.
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowVoiceModal(true)}
          className="shrink-0 flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold px-4 py-2.5 rounded-xl text-xs transition-all shadow-lg hover:shadow-emerald-500/20 hover:scale-[1.02]"
        >
          <Mic size={14} />
          <span>Open Nutrition Coach</span>
          <span className="text-xs font-mono">→</span>
        </button>
      </div>

      {/* Manual Meal Form */}
      {showMealForm && (
        <form onSubmit={handleAddMeal} className="bg-[#0f1a0f] border border-emerald-500/40 rounded-xl p-5 space-y-4 shadow-xl">
          <h3 className="text-sm font-bold text-white">Log Nutrition Entry to SQLite</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Meal Type</label>
              <select
                value={mealInput.meal_type}
                onChange={e => setMealInput({ ...mealInput, meal_type: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
              >
                <option value="BREAKFAST">Breakfast</option>
                <option value="LUNCH">Lunch</option>
                <option value="DINNER">Dinner</option>
                <option value="SNACK">Snack</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-emerald-400 block mb-1">Food Description</label>
              <input
                type="text"
                placeholder="e.g. Grilled salmon, brown rice and steamed broccoli"
                value={mealInput.food_description}
                onChange={e => setMealInput({ ...mealInput, food_description: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
                required
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Portion Size</label>
              <input
                type="text"
                placeholder="e.g. 1 plate, 1 bowl"
                value={mealInput.portion}
                onChange={e => setMealInput({ ...mealInput, portion: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowMealForm(false)}
              className="px-3 py-1.5 text-xs text-emerald-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium shadow-md"
            >
              {submitting ? 'Saving...' : 'Save Meal'}
            </button>
          </div>
        </form>
      )}

      {/* 4 Nutrition Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Hydration Target */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Daily Hydration</span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white font-mono">
              {profile.water_intake_liters ? `${profile.water_intake_liters}L` : '2.0L'}
            </span>
            <span className="text-xs text-emerald-400 font-mono">Target</span>
          </div>
          <p className="text-[11px] text-emerald-400/90 font-mono">
            {profile.water_intake_liters >= 2.0 ? 'Optimal hydration status' : 'Tracking recommended'}
          </p>
        </div>

        {/* Metric 2: Today's Logging Adherence */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Logging Adherence</span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white font-mono">{adherencePct}%</span>
            <span className="text-xs text-emerald-400 font-mono">({mealCount}/3 meals)</span>
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Based on today's SQLite logs</p>
        </div>

        {/* Metric 3: Fruit & Veg Intake */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Produce Target</span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white font-mono">
              {profile.fruit_veg_servings ? `${profile.fruit_veg_servings}` : '5'}
            </span>
            <span className="text-xs text-emerald-400 font-mono">servings/day</span>
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Micronutrient &amp; fiber density</p>
        </div>

        {/* Metric 4: Dietary Restrictions */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Dietary Profile</span>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-emerald-300">
              {profile.food_restrictions && profile.food_restrictions !== 'None' ? profile.food_restrictions : 'Whole-Food Protocol'}
            </span>
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">
            Allergies: {profile.allergies || 'None recorded'}
          </p>
        </div>
      </div>

      {/* Scheduled Daily Meal Plan Card (Created by AI or Orchestrator) */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <CalendarCheck size={18} />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Today's Scheduled Meal Routine</h3>
              <p className="text-xs text-emerald-100/60">Structured daily timeline prepared by your nutrition specialist</p>
            </div>
          </div>

          <button
            onClick={() => setShowVoiceModal(true)}
            className="text-xs font-mono text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 px-3 py-1.5 rounded-lg border border-emerald-500/30 transition-colors flex items-center gap-1.5"
          >
            <Sparkles size={12} />
            <span>Ask Coach to Regenerate Schedule</span>
          </button>
        </div>

        {!hasScheduledMeals ? (
          <div className="py-8 text-center border border-dashed border-emerald-900/40 rounded-lg text-xs text-emerald-100/60 space-y-2">
            <p>No scheduled meals found in your active Daily Health Plan.</p>
            <button
              onClick={() => setShowVoiceModal(true)}
              className="text-emerald-400 font-semibold underline block mx-auto"
            >
              Ask the Voice Coach: "Prepare my meal schedule for today" →
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {scheduledPlanMeals.map((meal) => (
              <div
                key={meal.id}
                className="p-4 bg-[#111a11] border border-emerald-900/50 rounded-xl space-y-2 flex flex-col justify-between"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-1">
                      <Clock size={10} />
                      {meal.time_block}
                    </span>
                    {meal.dosage && (
                      <span className="text-[10px] font-mono text-emerald-300">
                        {meal.dosage}
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-bold text-white">{meal.activity_title}</h4>
                  {meal.instructions && (
                    <p className="text-xs text-emerald-100/70 leading-relaxed">
                      {meal.instructions}
                    </p>
                  )}
                </div>

                {meal.caution && (
                  <p className="text-[10px] text-amber-400/90 font-mono bg-amber-500/10 p-1.5 rounded border border-amber-500/20">
                    ℹ️ {meal.caution}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main Grid: Today's Meal Logs + Practical Guidance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Logged Meals */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Your Nutrition Audit Log</h3>
              <p className="text-xs text-emerald-100/60">Persistent meal records saved in SQLite</p>
            </div>
            <span className="text-xs font-mono text-emerald-400">{meals.length} entries recorded</span>
          </div>

          {!hasMeals ? (
            <div className="py-8 text-center border border-dashed border-emerald-900/40 rounded-lg text-xs text-emerald-100/60 space-y-2">
              <p>No meals logged yet in the database.</p>
              <button
                onClick={() => setShowVoiceModal(true)}
                className="text-emerald-400 font-semibold underline block mx-auto"
              >
                Log your first meal with Voice Coach →
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {meals.slice(0, 8).map((m) => (
                <div key={m.id} className="p-3.5 bg-[#111a11] border border-emerald-900/40 rounded-lg flex items-center justify-between gap-3">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">{m.food_description}</span>
                      <span className="text-[10px] font-mono text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                        {m.meal_type}
                      </span>
                    </div>
                    <p className="text-[11px] text-emerald-100/60 font-mono">
                      Portion: {m.portion || 'Standard'} {m.logged_at ? `• ${m.logged_at.substring(0, 16)}` : ''}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteMeal(m.id)}
                    className="text-emerald-700 hover:text-red-400 transition-colors p-1"
                    title="Remove log"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Nutritional Prescriptions */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Clinical Nutrition Guidance</h3>
              <p className="text-xs text-emerald-100/60">Tailored to support connective tissue adaptation</p>
            </div>
            <span className="text-xs font-mono text-emerald-400">Tissue Remodeling</span>
          </div>

          <div className="space-y-3">
            {[
              {
                title: 'Collagen & Vitamin C Timing',
                desc: 'Consume a Vitamin C rich fruit (orange/berries) 45 min before physical therapy to maximize tendon collagen synthesis.',
                badge: 'Connective Tissue'
              },
              {
                title: 'Post-Activity Protein',
                desc: 'Aim for 20-30g of protein (Greek yogurt, eggs, or fish) within 90 minutes of your workout to support muscle recovery.',
                badge: 'Muscle Recovery'
              },
              {
                title: 'Hydration Osmolality',
                desc: 'Add a pinch of Celtic sea salt or electrolyte trace minerals to your first 500ml of morning water to enhance intracellular hydration.',
                badge: 'Cellular Reset'
              }
            ].map((g, i) => (
              <div key={i} className="p-3.5 bg-[#111a11] border border-emerald-900/40 rounded-lg space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{g.title}</span>
                  <span className="text-[10px] text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded">
                    {g.badge}
                  </span>
                </div>
                <p className="text-[11px] text-emerald-100/70">{g.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Voice Nutrition Coach Modal */}
      <NutritionVoiceAgentModal
        isOpen={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        onPlanUpdated={() => fetchMeals(true)}
      />
    </div>
  );
}
