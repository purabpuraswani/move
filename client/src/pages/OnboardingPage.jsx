import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Heart, ChevronRight, ChevronLeft, Check, ShieldCheck,
  User, Dumbbell, Apple, Brain, Moon, FileText, ArrowRight
} from 'lucide-react';
import { profileService, workflowService } from '../services/api';
import { useAuth } from '../App';

const STEPS = [
  { id: 1, title: 'Personal Profile', icon: User },
  { id: 2, title: 'Exercise & Lifestyle', icon: Dumbbell },
  { id: 3, title: 'Nutrition Patterns', icon: Apple },
  { id: 4, title: 'Daily Behaviour', icon: Brain },
  { id: 5, title: 'Recovery & Sleep', icon: Moon },
  { id: 6, title: 'Clinical Health Screening', icon: ShieldCheck },
  { id: 7, title: 'Review & Confirm', icon: FileText },
];

export default function OnboardingPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [completedSummary, setCompletedSummary] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    // Step 1: Personal
    name: user?.name || '',
    date_of_birth: '',
    height: '',
    weight: '',
    work_pattern: 'OFFICE',
    primary_goal: 'Improve mobility and posture',
    activity_preferences: 'Walking, Stretching',

    // Step 2: Exercise & Lifestyle
    daily_steps: '',
    exercise_frequency: '',
    exercise_minutes: '',
    exercise_type: 'Walking',
    sitting_hours: '',
    walking_frequency: 'Daily',
    movement_breaks: '',
    current_activity_habits: 'Short daily walks',

    // Step 3: Nutrition
    typical_breakfast: '',
    typical_lunch: '',
    typical_dinner: '',
    snacks: '',
    meals_per_day: '3',
    water_intake_liters: '',
    fruit_veg_servings: '',
    food_preferences: 'Whole foods',
    allergies: 'None',
    dietary_restrictions: 'None',
    nutrition_goals: 'Hydration and balanced meals',

    // Step 4: Behaviour
    existing_habits: '',
    motivation: '',
    main_barriers: '',
    work_routine: 'Standard office desk hours',
    preferred_reminders: 'Hourly breaks',
    habits_to_improve: 'Reduce prolonged sitting',

    // Step 5: Recovery
    sleep_duration: '',
    sleep_quality: 'GOOD',
    stress_level: '3',
    rest_days: '2',
    recovery_habits: 'Gentle evening stretching',

    // Step 6: Health Screening (YES / NO / UNKNOWN)
    diabetes: 'UNKNOWN',
    hypertension: 'UNKNOWN',
    heart_condition: 'UNKNOWN',
    injury_history: 'UNKNOWN',
    joint_pain: 'UNKNOWN',
    back_pain: 'UNKNOWN',
    neck_pain: 'UNKNOWN',
    other_conditions: '',
    medical_notes: ''
  });

  const update = (key, val) => setFormData(p => ({ ...p, [key]: val }));

  const handleNext = () => {
    if (currentStep < 7) {
      setCurrentStep(s => s + 1);
      window.scrollTo(0, 0);
    } else {
      handleFinalSubmit();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(s => s - 1);
      window.scrollTo(0, 0);
    }
  };

  const handleFinalSubmit = async () => {
    setSaving(true);
    setError('');

    try {
      const payload = {
        name: formData.name || undefined,
        date_of_birth: formData.date_of_birth || undefined,
        height: formData.height ? parseFloat(formData.height) : null,
        weight: formData.weight ? parseFloat(formData.weight) : null,
        work_pattern: formData.work_pattern,
        wellness_goals: [formData.primary_goal, formData.habits_to_improve].filter(Boolean),
        activity_preferences: [formData.activity_preferences, formData.exercise_type].filter(Boolean),
        daily_steps: formData.daily_steps ? parseInt(formData.daily_steps) : null,
        sitting_hours: formData.sitting_hours ? parseFloat(formData.sitting_hours) : null,
        movement_breaks: formData.movement_breaks ? parseInt(formData.movement_breaks) : null,
        exercise_frequency: formData.exercise_frequency ? parseInt(formData.exercise_frequency) : null,
        exercise_minutes: formData.exercise_minutes ? parseInt(formData.exercise_minutes) : null,
        exercise_types: [formData.exercise_type].filter(Boolean),
        food_preferences: formData.food_preferences,
        food_restrictions: formData.dietary_restrictions,
        allergies: formData.allergies,
        water_intake_liters: formData.water_intake_liters ? parseFloat(formData.water_intake_liters) : null,
        fruit_veg_servings: formData.fruit_veg_servings ? parseInt(formData.fruit_veg_servings) : null,
        nutrition_goals: formData.nutrition_goals,
        motivation: formData.motivation,
        barriers: formData.main_barriers,
        existing_habits: formData.existing_habits,
        preferred_changes: formData.habits_to_improve,
        sleep_hours: formData.sleep_duration ? parseFloat(formData.sleep_duration) : null,
        sleep_quality: formData.sleep_quality,
        stress_level: formData.stress_level ? parseInt(formData.stress_level) : null,
        onboarding_completed: 1,

        // Health screening with explicit YES / NO / UNKNOWN
        diabetes: formData.diabetes,
        hypertension: formData.hypertension,
        heart_condition: formData.heart_condition,
        injury_history: formData.injury_history,
        joint_pain: formData.joint_pain,
        back_pain: formData.back_pain,
        neck_pain: formData.neck_pain,
        other_conditions: [formData.other_conditions, formData.medical_notes].filter(Boolean).join('; ')
      };

      await profileService.update(payload);

      // Automatically run workflow to synthesize first user plan from real input
      try {
        await workflowService.run();
      } catch (wfErr) {
        console.warn('Initial workflow notice:', wfErr);
      }

      const updatedUser = { ...user, onboarding_completed: 1 };
      login(updatedUser, localStorage.getItem('movewell_token'));
      setCompletedSummary(true);
    } catch (err) {
      console.error('Onboarding submission error:', err);
      setError(err.response?.data?.error || 'Failed to save profile. Please check your inputs.');
    } finally {
      setSaving(false);
    }
  };

  if (completedSummary) {
    return (
      <div className="min-h-screen bg-[#0a0f0a] flex items-center justify-center p-4">
        <div className="bg-[#0f1a0f] border border-emerald-500/40 rounded-2xl p-8 max-w-xl w-full text-center space-y-6 shadow-2xl">
          <div className="w-16 h-16 bg-emerald-500/20 border border-emerald-500 rounded-full flex items-center justify-center mx-auto text-emerald-400">
            <Check size={32} />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-white">Profile Onboarding Complete!</h2>
            <p className="text-sm text-emerald-100/70">
              Your genuine health screening and lifestyle parameters have been saved to your local SQLite database.
            </p>
          </div>

          <div className="p-4 bg-[#111a11] border border-emerald-900/40 rounded-xl text-left text-xs font-mono space-y-2">
            <div className="text-emerald-400 font-bold uppercase tracking-wider">Next Recommended Step:</div>
            <p className="text-emerald-100/80">
              Perform your baseline <strong className="text-white">Movement Assessment</strong> using the MoveNet camera sensor or manual entry. This unlocks your personalized Physiotherapy range-of-motion protocol.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Link
              to="/assessment"
              className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
            >
              <span>Take Movement Assessment</span>
              <ArrowRight size={15} />
            </Link>
            <Link
              to="/dashboard"
              className="flex-1 bg-[#111a11] hover:bg-emerald-500/10 border border-emerald-900 text-emerald-300 font-medium py-3 rounded-xl text-sm transition-colors"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0f0a] text-white p-4 md:p-8">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-full text-emerald-400 text-xs font-mono">
            <Heart size={14} />
            <span>MoveWell AI • Clinical Lifestyle Setup</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Personal Wellness Onboarding</h1>
          <p className="text-xs md:text-sm text-emerald-100/60">
            Step {currentStep} of 7: {STEPS[currentStep - 1].title}
          </p>
        </div>

        {/* Multi-step progress bar */}
        <div className="grid grid-cols-7 gap-1">
          {STEPS.map((s) => (
            <div
              key={s.id}
              className={`h-1.5 rounded-full transition-all ${
                s.id <= currentStep ? 'bg-emerald-500' : 'bg-neutral-800'
              }`}
            />
          ))}
        </div>

        {/* Form Card */}
        <div className="bg-[#0f1a0f] border border-emerald-900/50 rounded-2xl p-6 md:p-8 shadow-xl space-y-6">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs flex items-center gap-2">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: Personal Profile */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <User size={18} className="text-emerald-400" />
                <span>Step 1: Personal Profile</span>
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Full Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Jordan Smith"
                    value={formData.name}
                    onChange={e => update('name', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Date of Birth</label>
                  <input
                    type="date"
                    value={formData.date_of_birth}
                    onChange={e => update('date_of_birth', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Height (cm)</label>
                  <input
                    type="number"
                    placeholder="e.g. 175"
                    value={formData.height}
                    onChange={e => update('height', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Weight (kg)</label>
                  <input
                    type="number"
                    step="0.5"
                    placeholder="e.g. 72"
                    value={formData.weight}
                    onChange={e => update('weight', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Work Pattern</label>
                <select
                  value={formData.work_pattern}
                  onChange={e => update('work_pattern', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                >
                  <option value="OFFICE">Office / Desk Seated (&gt; 6 hrs/day)</option>
                  <option value="HYBRID">Hybrid (Mix of Seated &amp; Standing)</option>
                  <option value="ACTIVE">Active / On Feet Most of the Day</option>
                  <option value="MANUAL">Physical / Manual Labour</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Primary Wellness Goal</label>
                <input
                  type="text"
                  placeholder="e.g. Eliminate lower back stiffness and improve daily energy"
                  value={formData.primary_goal}
                  onChange={e => update('primary_goal', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                />
              </div>
            </div>
          )}

          {/* STEP 2: Exercise & Lifestyle */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Dumbbell size={18} className="text-emerald-400" />
                <span>Step 2: Exercise &amp; Physical Activity</span>
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Average Daily Steps (estimate)</label>
                  <input
                    type="number"
                    placeholder="e.g. 7000 (or leave blank if unsure)"
                    value={formData.daily_steps}
                    onChange={e => update('daily_steps', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Exercise Days per Week (0-7)</label>
                  <input
                    type="number"
                    min="0"
                    max="7"
                    placeholder="e.g. 3"
                    value={formData.exercise_frequency}
                    onChange={e => update('exercise_frequency', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Typical Exercise Duration (Minutes)</label>
                  <input
                    type="number"
                    placeholder="e.g. 40"
                    value={formData.exercise_minutes}
                    onChange={e => update('exercise_minutes', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Daily Sitting Time (Hours)</label>
                  <input
                    type="number"
                    step="0.5"
                    placeholder="e.g. 8"
                    value={formData.sitting_hours}
                    onChange={e => update('sitting_hours', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Movement Breaks per Working Day</label>
                <input
                  type="number"
                  placeholder="e.g. 3 breaks (or leave blank if unsure)"
                  value={formData.movement_breaks}
                  onChange={e => update('movement_breaks', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Preferred Exercise / Movement Types</label>
                <input
                  type="text"
                  placeholder="e.g. Brisk walking, cycling, yoga, bodyweight strength"
                  value={formData.exercise_type}
                  onChange={e => update('exercise_type', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                />
              </div>
            </div>
          )}

          {/* STEP 3: Nutrition */}
          {currentStep === 3 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Apple size={18} className="text-emerald-400" />
                <span>Step 3: Nutrition Patterns &amp; Intake</span>
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Daily Water Intake (Litres)</label>
                  <input
                    type="number"
                    step="0.2"
                    placeholder="e.g. 1.8"
                    value={formData.water_intake_liters}
                    onChange={e => update('water_intake_liters', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Fruit &amp; Veg Servings / Day</label>
                  <input
                    type="number"
                    placeholder="e.g. 3"
                    value={formData.fruit_veg_servings}
                    onChange={e => update('fruit_veg_servings', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Typical Breakfast</label>
                  <input
                    type="text"
                    placeholder="e.g. Oatmeal &amp; coffee"
                    value={formData.typical_breakfast}
                    onChange={e => update('typical_breakfast', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Typical Lunch</label>
                  <input
                    type="text"
                    placeholder="e.g. Salad with chicken"
                    value={formData.typical_lunch}
                    onChange={e => update('typical_lunch', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Typical Dinner</label>
                  <input
                    type="text"
                    placeholder="e.g. Rice, salmon, veg"
                    value={formData.typical_dinner}
                    onChange={e => update('typical_dinner', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-xs text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Food Allergies (or None)</label>
                  <input
                    type="text"
                    placeholder="e.g. None, Peanuts, Shellfish"
                    value={formData.allergies}
                    onChange={e => update('allergies', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Dietary Restrictions</label>
                  <input
                    type="text"
                    placeholder="e.g. Vegetarian, Gluten-free, Low-sodium"
                    value={formData.dietary_restrictions}
                    onChange={e => update('dietary_restrictions', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: Behaviour & Daily Habits */}
          {currentStep === 4 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Brain size={18} className="text-emerald-400" />
                <span>Step 4: Behaviour &amp; Habitual Routines</span>
              </h2>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Primary Motivation</label>
                <input
                  type="text"
                  placeholder="e.g. Stay active with my kids and avoid desk-related posture fatigue"
                  value={formData.motivation}
                  onChange={e => update('motivation', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                />
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Main Barriers to Movement</label>
                <input
                  type="text"
                  placeholder="e.g. Back-to-back meetings, fatigue at end of day, forgetting to take breaks"
                  value={formData.main_barriers}
                  onChange={e => update('main_barriers', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                />
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Existing Positive Daily Habits</label>
                <input
                  type="text"
                  placeholder="e.g. Morning glass of water, walking the dog at 7 AM"
                  value={formData.existing_habits}
                  onChange={e => update('existing_habits', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                />
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Habits You Want to Build / Improve</label>
                <input
                  type="text"
                  placeholder="e.g. 5-minute hourly desk breaks, evening wind-down routine"
                  value={formData.habits_to_improve}
                  onChange={e => update('habits_to_improve', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                />
              </div>
            </div>
          )}

          {/* STEP 5: Recovery & Sleep */}
          {currentStep === 5 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Moon size={18} className="text-emerald-400" />
                <span>Step 5: Recovery, Sleep &amp; Stress</span>
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Average Sleep Duration (Hours)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="3"
                    max="14"
                    placeholder="e.g. 7.5"
                    value={formData.sleep_duration}
                    onChange={e => update('sleep_duration', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Subjective Sleep Quality</label>
                  <select
                    value={formData.sleep_quality}
                    onChange={e => update('sleep_quality', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                  >
                    <option value="EXCELLENT">Excellent (Wake up completely energized)</option>
                    <option value="GOOD">Good (Restful sleep most nights)</option>
                    <option value="FAIR">Fair (Occasional awakenings / mild fatigue)</option>
                    <option value="POOR">Poor (Frequent insomnia / restless sleep)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Average Daily Stress Level (1-10)</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    placeholder="e.g. 4"
                    value={formData.stress_level}
                    onChange={e => update('stress_level', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-400 block mb-1">Rest Days per Week</label>
                  <input
                    type="number"
                    min="0"
                    max="7"
                    placeholder="e.g. 2"
                    value={formData.rest_days}
                    onChange={e => update('rest_days', e.target.value)}
                    className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Current Recovery Habits</label>
                <input
                  type="text"
                  placeholder="e.g. Evening walks, foam rolling, dark-room breathing"
                  value={formData.recovery_habits}
                  onChange={e => update('recovery_habits', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-sm text-white"
                />
              </div>
            </div>
          )}

          {/* STEP 6: Health Screening */}
          {currentStep === 6 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <ShieldCheck size={18} className="text-emerald-400" />
                  <span>Step 6: Clinical Health Screening (Physiotherapy Safety Gate)</span>
                </h2>
                <p className="text-xs text-emerald-100/60 mt-1">
                  Answer honestly. Unanswered or unknown questions remain UNKNOWN to protect clinical safety thresholds.
                </p>
              </div>

              <div className="space-y-3">
                {[
                  { key: 'diabetes', label: 'Diabetes or Glucose Regulation Condition' },
                  { key: 'hypertension', label: 'Hypertension or High Blood Pressure' },
                  { key: 'heart_condition', label: 'Diagnosed Heart or Cardiovascular Condition' },
                  { key: 'injury_history', label: 'Recent Musculoskeletal Injury (Past 12 Months)' },
                  { key: 'joint_pain', label: 'Current or Recurring Joint Pain' },
                  { key: 'back_pain', label: 'Chronic Lumbar / Lower Back Pain' },
                  { key: 'neck_pain', label: 'Cervical / Neck & Shoulder Pain' }
                ].map(({ key, label }) => (
                  <div key={key} className="p-3 bg-[#111a11] rounded-xl border border-emerald-900/30 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white">{label}</span>
                    <div className="flex gap-1.5">
                      {['YES', 'NO', 'UNKNOWN'].map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => update(key, opt)}
                          className={`px-3 py-1 rounded text-xs font-mono font-bold transition-colors ${
                            formData[key] === opt
                              ? opt === 'YES'
                                ? 'bg-amber-500 text-black'
                                : opt === 'NO'
                                ? 'bg-emerald-500 text-black'
                                : 'bg-emerald-900 text-emerald-200'
                              : 'bg-[#0a0f0a] text-emerald-700 hover:text-emerald-400'
                          }`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div>
                <label className="text-xs text-emerald-400 block mb-1">Optional Description of Any Medical Condition or Surgery</label>
                <textarea
                  rows="2"
                  placeholder="e.g. Mild right knee sprain in 2021, fully healed. Occasional morning neck tightness."
                  value={formData.other_conditions}
                  onChange={e => update('other_conditions', e.target.value)}
                  className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-xs text-white"
                />
              </div>
            </div>
          )}

          {/* STEP 7: Review & Confirm */}
          {currentStep === 7 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <FileText size={18} className="text-emerald-400" />
                  <span>Step 7: Review Your Wellness Profile</span>
                </h2>
                <p className="text-xs text-emerald-100/60 mt-1">
                  Verify your profile details before saving. All entries are persisted to SQLite and analyzed by the six specialist domains.
                </p>
              </div>

              <div className="space-y-3 text-xs font-mono">
                {/* Personal Review */}
                <div className="p-3 bg-[#111a11] rounded-xl border border-emerald-900/40 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <span className="text-emerald-400 font-bold block">1. Personal Profile</span>
                    <span className="text-white">Name: {formData.name || 'Not provided'} • DOB: {formData.date_of_birth || 'Not provided'}</span>
                    <span className="text-emerald-100/70 block">Height: {formData.height || '—'} cm • Weight: {formData.weight || '—'} kg • Work: {formData.work_pattern}</span>
                  </div>
                  <button onClick={() => setCurrentStep(1)} className="text-emerald-400 underline text-[11px]">Edit</button>
                </div>

                {/* Exercise Review */}
                <div className="p-3 bg-[#111a11] rounded-xl border border-emerald-900/40 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <span className="text-emerald-400 font-bold block">2. Exercise &amp; Activity</span>
                    <span className="text-white">Steps: {formData.daily_steps || 'Unsure'} • Exercise: {formData.exercise_frequency || '0'} days/wk × {formData.exercise_minutes || '0'} min</span>
                    <span className="text-emerald-100/70 block">Sitting: {formData.sitting_hours || '—'} hrs/day • Movement Breaks: {formData.movement_breaks || '—'}</span>
                  </div>
                  <button onClick={() => setCurrentStep(2)} className="text-emerald-400 underline text-[11px]">Edit</button>
                </div>

                {/* Nutrition Review */}
                <div className="p-3 bg-[#111a11] rounded-xl border border-emerald-900/40 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <span className="text-emerald-400 font-bold block">3. Nutrition &amp; Hydration</span>
                    <span className="text-white">Water: {formData.water_intake_liters || '—'} L • Fruit/Veg: {formData.fruit_veg_servings || '—'} servings</span>
                    <span className="text-emerald-100/70 block">Allergies: {formData.allergies} • Restrictions: {formData.dietary_restrictions}</span>
                  </div>
                  <button onClick={() => setCurrentStep(3)} className="text-emerald-400 underline text-[11px]">Edit</button>
                </div>

                {/* Recovery Review */}
                <div className="p-3 bg-[#111a11] rounded-xl border border-emerald-900/40 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <span className="text-emerald-400 font-bold block">4. Recovery &amp; Sleep</span>
                    <span className="text-white">Sleep: {formData.sleep_duration || '—'} hrs ({formData.sleep_quality}) • Stress: {formData.stress_level}/10</span>
                  </div>
                  <button onClick={() => setCurrentStep(5)} className="text-emerald-400 underline text-[11px]">Edit</button>
                </div>

                {/* Health Screening Review */}
                <div className="p-3 bg-[#111a11] rounded-xl border border-emerald-900/40 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <span className="text-emerald-400 font-bold block">5. Safety Gate Health Screening</span>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-[11px] pt-1">
                      <span>Heart: <strong className={formData.heart_condition === 'YES' ? 'text-amber-400' : 'text-emerald-300'}>{formData.heart_condition}</strong></span>
                      <span>Hypertension: <strong className={formData.hypertension === 'YES' ? 'text-amber-400' : 'text-emerald-300'}>{formData.hypertension}</strong></span>
                      <span>Joint Pain: <strong className={formData.joint_pain === 'YES' ? 'text-amber-400' : 'text-emerald-300'}>{formData.joint_pain}</strong></span>
                      <span>Back Pain: <strong className={formData.back_pain === 'YES' ? 'text-amber-400' : 'text-emerald-300'}>{formData.back_pain}</strong></span>
                      <span>Neck Pain: <strong className={formData.neck_pain === 'YES' ? 'text-amber-400' : 'text-emerald-300'}>{formData.neck_pain}</strong></span>
                      <span>Injuries: <strong className={formData.injury_history === 'YES' ? 'text-amber-400' : 'text-emerald-300'}>{formData.injury_history}</strong></span>
                    </div>
                  </div>
                  <button onClick={() => setCurrentStep(6)} className="text-emerald-400 underline text-[11px]">Edit</button>
                </div>
              </div>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-emerald-900/40">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handleBack}
                className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-white px-3 py-2 rounded-lg border border-emerald-900/60"
              >
                <ChevronLeft size={14} />
                <span>Back</span>
              </button>
            ) : <div />}

            <button
              type="button"
              onClick={handleNext}
              disabled={saving}
              className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-6 py-2.5 rounded-xl text-xs flex items-center gap-1.5 transition-colors shadow-lg"
            >
              <span>{saving ? 'Saving to Database...' : currentStep === 7 ? 'Confirm & Save Profile' : 'Continue'}</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
