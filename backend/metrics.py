import time

class PerformanceMetrics:
    def __init__(self):
        self.start_time = 0.0

    def start_timer(self):
        self.start_time = time.perf_counter()

    def stop_timer(self):
        end_time = time.perf_counter()
        return end_time - self.start_time

    def calculate_rtf(self, stt_latency: float, audio_duration: float):
        """
        Real-Time Factor (RTF) = Processing Time / Audio Duration.
        RTF < 1.0 means it processes faster than real-time.
        """
        if audio_duration <= 0:
            return 0.0
        return stt_latency / audio_duration

    def log_metrics(self, session_id: str, request_type: str, total_latency: float, llm_latency: float, stt_latency: float = 0.0, rtf: float = 0.0):
        report = f"--- [{request_type}] Session: {session_id} ---\n"
        report += f"Total Turnaround Latency: {total_latency:.2f}s\n"
        report += f"LLM Generation Latency: {llm_latency:.2f}s\n"
        if request_type == "Voice":
            report += f"STT Engine Latency: {stt_latency:.2f}s\n"
            report += f"STT Real-Time Factor (RTF): {rtf:.2f}\n"
        report += "\n"
        
        with open("metrics_report.txt", "a") as f:
            f.write(report)
