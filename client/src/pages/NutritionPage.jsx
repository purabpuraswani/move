import React, { useEffect, useState } from 'react';
import {
  Apple, Droplet, CheckCircle, Plus, Trash2, ShieldCheck,
  TrendingUp, AlertCircle, Utensils
} from 'lucide-react';
import { mealService, profileService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function NutritionPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showMealForm, setShowMealForm] = useState(false);
  const [mealInput, setMealInput] = useState({
    meal_type: 'LUNCH',
    food_description: '',
    portion: '1 plate',
    calories_optional: ''
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchMeals = async () => {
    try {
      setLoading(true);
      const res = await mealService.getAll();
      setData(res.data);
    } catch (err) {
      console.error('Error fetching meals:', err);
    } finally {
      setLoading(false);
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
      await fetchMeals();
    } catch (err) {
      console.error('Error deleting meal:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Nutrition &amp; Metabolic Protocol from SQLite..." />
      </div>
    );
  }

  const meals = data?.meals || [];
  const profile = data?.profile || {};
  const hasMeals = meals.length > 0;

  const todayStr = new Date().toISOString().substring(0, 10);
  const todayMeals = meals.filter(m => m.logged_at?.substring(0, 10) === todayStr);
  const mealCount = todayMeals.length;
  const adherencePct = Math.min(100, Math.round((mealCount / 3) * 100));

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Title */}
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

        <button
          onClick={() => setShowMealForm(!showMealForm)}
          className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg"
        >
          <Plus size={15} />
          <span>Log Meal / Snack</span>
        </button>
      </div>

      {/* Log Meal Form */}
      {showMealForm && (
        <form onSubmit={handleAddMeal} className="bg-[#0f1a0f] border border-emerald-500/40 rounded-xl p-5 space-y-4 shadow-xl">
          <h3 className="text-sm font-bold text-white">Log Nutrition Entry to SQLite</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Meal Type</label>
              <select
                value={mealInput.meal_type}
                onChange={e => setMealInput({ ...mealInput, meal_type: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
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
                placeholder="e.g. Grilled chicken salad with olive oil &amp; quinoa"
                value={mealInput.food_description}
                onChange={e => setMealInput({ ...mealInput, food_description: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
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
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowMealForm(false)} className="px-3 py-1.5 text-xs text-emerald-400">Cancel</button>
            <button type="submit" disabled={submitting} className="px-4 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg">
              {submitting ? 'Saving to SQLite...' : 'Save Meal Log'}
            </button>
          </div>
        </form>
      )}

      {/* 4 Nutrition Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Hydration */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Daily Hydration</span>
          <div className="flex items-baseline gap-2">
            {profile.water_intake_liters ? (
              <>
                <span className="text-3xl font-bold text-white font-mono">{profile.water_intake_liters} L</span>
                <span className="text-xs text-emerald-500 font-mono">/ 2.5 L</span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT SET</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-400 font-mono">
            {profile.water_intake_liters ? 'Target logged in profile' : 'Set hydration target in profile'}
          </p>
        </div>

        {/* Metric 2: Fruit & Veg */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Fruit &amp; Veg Servings</span>
          <div className="flex items-baseline gap-2">
            {profile.fruit_veg_servings ? (
              <>
                <span className="text-3xl font-bold text-white font-mono">{profile.fruit_veg_servings} / 5</span>
                <span className="text-xs text-emerald-400 font-semibold">Servings</span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT SET</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Micronutrient dense intake</p>
        </div>

        {/* Metric 3: Meal Pattern Adherence */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Meal Pattern Adherence</span>
          <div className="flex items-baseline gap-2">
            {hasMeals ? (
              <span className="text-3xl font-bold text-white font-mono">{adherencePct}%</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-400 font-mono">
            {mealCount > 0 ? `${mealCount} / 3 main meals logged today` : 'No meals logged today'}
          </p>
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

      {/* Main Grid: Today's Meal Logs + Practical Guidance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Logged Meals */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Your Nutrition Log</h3>
              <p className="text-xs text-emerald-100/60">Persistent meal records from SQLite</p>
            </div>
            <span className="text-xs font-mono text-emerald-400">{meals.length} entries recorded</span>
          </div>

          {!hasMeals ? (
            <div className="py-8 text-center border border-dashed border-emerald-900/40 rounded-lg text-xs text-emerald-100/60 space-y-2">
              <p>No meals logged yet in the database.</p>
              <button
                onClick={() => setShowMealForm(true)}
                className="text-emerald-400 font-semibold underline block mx-auto"
              >
                Log your first meal / snack →
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
    </div>
  );
}
